# app/services/lead_service.py
"""
Module: Lead Service
Context: Pod B - Business Logic Layer.

Orchestrates the lifecycle of Leads, including creation, listing, and the critical
'promote_to_deal' workflow.
Uses dependency injection for Repositories and the Event Bus.

SECURITY CONTROLS:
- Duplicate email detection (prevents duplicate leads)
- Owner validation (ensures owner exists and belongs to tenant)
- State lock on converted leads (prevents editing immutable leads)
"""

import asyncio
import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import Event Bus Bridge
from app.core.event_bus import event_bus, get_main_loop

# Import Models, Schemas, and Events
from app.schemas.crm import LeadCreate, LeadUpdate
from app.models.crm import Lead, Deal
from app.models.auth import User
from app.events.crm_events import DealCreated

# Import Repositories
from app.repos.lead_repo import LeadRepo
from app.repos.deal_repo import DealRepo

logger = logging.getLogger(__name__)

class LeadService:
    """
    Service class containing pure business logic for Leads.
    """
    def __init__(self, db: Session):
        """
        Initialize the service with a DB session.
        Instantiates required Repositories immediately.
        
        Args:
            db (Session): The active SQLAlchemy session.
        """
        self.db = db
        self.lead_repo = LeadRepo(db)
        self.deal_repo = DealRepo(db)

    def create_lead(self, tenant_id: int, owner_id: int, data: LeadCreate) -> Lead:
        """
        Creates a new lead using the LeadRepo.
        
        SECURITY VALIDATIONS:
        1. Duplicate Email Check: Prevents creating leads with duplicate emails
        2. Owner Validation: Ensures owner exists and belongs to the tenant
        
        Args:
            tenant_id (int): The tenant context.
            owner_id (int): The user creating the lead.
            data (LeadCreate): Validated input data.
            
        Returns:
            Lead: The persisted lead object.
            
        Raises:
            HTTPException: 400 if validation fails
        """
        # =====================================================================
        # SECURITY VALIDATION 1: Duplicate Email Check
        # =====================================================================
        if data.email:
            existing_lead = (
                self.db.query(Lead)
                .filter(
                    Lead.tenant_id == tenant_id,
                    Lead.email == data.email
                )
                .first()
            )
            
            if existing_lead:
                logger.warning(
                    f"Duplicate lead creation attempt: email '{data.email}' "
                    f"already exists for tenant {tenant_id} (Lead ID: {existing_lead.id})"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Lead with email '{data.email}' already exists."
                )
        
        # =====================================================================
        # SECURITY VALIDATION 2: Owner Validation
        # =====================================================================
        owner = self.db.query(User).filter(User.id == owner_id).first()
        
        if not owner:
            logger.warning(
                f"Invalid owner_id {owner_id} - user does not exist"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid owner_id: User does not exist."
            )
        
        if owner.tenant_id != tenant_id:
            logger.warning(
                f"Cross-tenant lead assignment attempt: owner {owner_id} "
                f"(tenant {owner.tenant_id}) cannot own lead in tenant {tenant_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid owner_id: User belongs to another tenant."
            )
        
        # All validations passed - create the lead
        lead = self.lead_repo.create(tenant_id, owner_id, data)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def list_leads(self, tenant_id: int, limit: int = 100, skip: int = 0) -> List[Lead]:
        """
        Retrieves a paginated list of leads for the tenant.
        
        Args:
            tenant_id (int): The tenant context.
            limit (int): Max records to return.
            skip (int): Pagination offset.
            
        Returns:
            List[Lead]: A list of lead objects.
        """
        return self.lead_repo.list_all(tenant_id, limit, skip)
    
    def update_lead(self, tenant_id: int, lead_id: int, updates: dict) -> Lead:
        """
        Updates a lead's details (name, email, status).
        
        SECURITY VALIDATION:
        - State Lock: Prevents editing converted leads (immutable)
        - Manual Conversion Bypass: Prevents patching status to 'converted' directly
        
        Args:
            tenant_id (int): Tenant context for isolation
            lead_id (int): ID of the lead to update
            updates (dict): Dictionary of fields to update
            
        Returns:
            Lead: Updated lead object
            
        Raises:
            HTTPException: 400 if lead is converted, if bypass attempted, or not found
        """
        # 1. Fetch the lead
        lead = self.lead_repo.get(lead_id, tenant_id)
        
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        # =====================================================================
        # SECURITY VALIDATION: State Lock on Converted Leads
        # =====================================================================
        # CRITICAL: Converted leads are immutable - they represent historical data
        # that has been promoted to a Deal. Allowing edits would break data integrity.
        if lead.status == "converted":
            logger.warning(
                f"Attempted edit of converted lead {lead_id} by tenant {tenant_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify a converted lead. Converted leads are immutable."
            )

        # SECURITY VALIDATION: Prevent manual conversion bypass
        if updates.get("status") == "converted":
            logger.warning(f"Attempted to bypass conversion workflow for lead {lead_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leads cannot be manually patched to 'converted'. Use the /convert endpoint."
            )
        
        # 3. Apply updates (only allowed fields)
        allowed_fields = {'name', 'email', 'status'}
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(lead, key, value)
        
        self.db.commit()
        self.db.refresh(lead)
        
        logger.info(f"Updated lead {lead_id} for tenant {tenant_id}")
        return lead

    def promote_to_deal(
        self, 
        tenant_id: int, 
        lead_id: int, 
        value_cents: int, 
        seller_id: Optional[int] = None
    ) -> Deal:
        """
        Atomic Workflow: Promote a Lead to a Deal.
        
        Business Rules:
        1. Lead must exist and belong to the tenant.
        2. Lead must not be already converted.
        3. Atomicity: DB Commit + Event Publication.
        
        Args:
            tenant_id (int): Context tenant.
            lead_id (int): ID of the lead to promote.
            value_cents (int): Value of the new deal.
            seller_id (Optional[int]): ID of the sales agent.
            
        Returns:
            Deal: The newly created deal.
            
        Raises:
            ValueError: If logic preconditions fail.
            SQLAlchemyError: If database persistence fails.
        """
        try:
            # 1. Fetch Lead (Read)
            lead = self.lead_repo.get(lead_id, tenant_id)
            if not lead:
                raise ValueError("Lead not found")

            # 2. Check Business Rule: Idempotency
            if lead.status == "converted":
                raise ValueError("Lead has already been converted")

            # 3. Create Deal (Write 1)
            # Note: Repo methods use 'flush' so we stay in the same transaction
            deal = self.deal_repo.create(
                tenant_id=tenant_id,
                lead_id=lead.id,
                value_cents=value_cents,
                seller_id=seller_id
            )

            # 4. Update Lead Status (Write 2)
            self.lead_repo.update_status(lead, "converted")
            
            # 5. Commit Transaction (Atomic DB Operation)
            self.db.commit()
            self.db.refresh(deal)
            
            # 6. Publish Domain Event (Fire-and-Forget)
            # Since this Service runs in a ThreadPool (Sync), we must dispatch
            # the event to the Main Asyncio Loop to allow background processing.
            event = DealCreated(
                tenant_id=tenant_id,
                deal_id=deal.id,
                lead_id=lead.id,
                value_cents=value_cents,
                seller_id=seller_id
            )
            
            main_loop = get_main_loop()
            if main_loop and main_loop.is_running():
                asyncio.run_coroutine_threadsafe(event_bus.publish(event), main_loop)
            
            return deal

        except SQLAlchemyError as e:
            # Rollback ensuring no partial data state (e.g. Deal created but Lead not updated)
            self.db.rollback()
            raise e