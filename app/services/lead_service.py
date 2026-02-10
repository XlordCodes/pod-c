# app/services/lead_service.py
"""
Module: Lead Service
Context: Pod B - Business Logic Layer.

Orchestrates the lifecycle of Leads, including creation, listing, and the critical
'promote_to_deal' workflow.
Uses dependency injection for Repositories and the Event Bus.
"""

import asyncio
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import Event Bus Bridge
from app.core.event_bus import event_bus, get_main_loop

# Import Models, Schemas, and Events
from app.schemas.crm import LeadCreate
from app.models.crm import Lead, Deal
from app.events.crm_events import DealCreated

# Import Repositories
from app.repos.lead_repo import LeadRepo
from app.repos.deal_repo import DealRepo

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
        
        Args:
            tenant_id (int): The tenant context.
            owner_id (int): The user creating the lead.
            data (LeadCreate): Validated input data.
            
        Returns:
            Lead: The persisted lead object.
        """
        return self.lead_repo.create(tenant_id, owner_id, data)

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