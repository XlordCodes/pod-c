# app/services/lead_service.py
"""
Module: Lead Service
Context: Pod B - Business Logic Layer.

Orchestrates the lifecycle of Leads, including creation, listing, and the critical
'promote_to_deal' workflow.
Uses dependency injection for Repositories to allow easy mocking in unit tests.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

# Import Models and Schemas
from app.schemas.crm import LeadCreate, LeadOut, DealOut
from app.models.crm import Lead, Deal

class LeadService:
    """
    Service class containing pure business logic for Leads.
    """
    def __init__(self, lead_repo_class, deal_repo_class, db_session: Session):
        """
        Initialize the service with Repository classes and a DB session.
        
        Args:
            lead_repo_class: The class definition for LeadRepo (not an instance).
            deal_repo_class: The class definition for DealRepo (not an instance).
            db_session (Session): The active SQLAlchemy session.
        """
        self.lead_repo_class = lead_repo_class
        self.deal_repo_class = deal_repo_class
        self.db = db_session

    def create_lead(self, tenant_id: int, owner_id: int, data: LeadCreate) -> LeadOut:
        """
        Creates a new lead using the injected LeadRepo.
        
        Args:
            tenant_id (int): Context tenant.
            owner_id (int): The user creating the lead.
            data (LeadCreate): Validated request data.
            
        Returns:
            Lead: The created lead object.
        """
        repo = self.lead_repo_class(self.db)
        # Note: 'create' method signature in LeadRepo matches this call
        return repo.create(tenant_id, data.name, data.email, owner_id)

    def list_leads(self, tenant_id: int, limit: int = 100, skip: int = 0) -> List[LeadOut]:
        """
        Retrieves a paginated list of leads for the tenant.
        
        Args:
            tenant_id (int): Context tenant.
            limit (int): Max records.
            skip (int): Pagination offset.
            
        Returns:
            List[Lead]: List of leads.
        """
        repo = self.lead_repo_class(self.db)
        return repo.list_all(tenant_id, limit, skip)

    def promote_to_deal(
        self, 
        tenant_id: int, 
        lead_id: int, 
        value_cents: int, 
        seller_id: Optional[int] = None
    ) -> DealOut:
        """
        Atomic Workflow: Promote a Lead to a Deal.
        
        Business Rules:
        1. Lead must exist and belong to the tenant.
        2. Lead must not be already converted.
        3. The creation of the Deal and the status update of the Lead must happen
           atomically (all or nothing).
           
        Args:
            tenant_id (int): Context tenant.
            lead_id (int): ID of the lead to promote.
            value_cents (int): Value of the new deal.
            seller_id (Optional[int]): ID of the sales agent.
            
        Returns:
            Deal: The newly created deal.
            
        Raises:
            ValueError: If logic preconditions fail (e.g., lead not found).
            SQLAlchemyError: If database persistence fails.
        """
        try:
            # Instantiate repos with the shared session
            lead_repo = self.lead_repo_class(self.db)
            deal_repo = self.deal_repo_class(self.db)

            # 1. Fetch Lead (Read)
            lead = lead_repo.get(lead_id, tenant_id)
            if not lead:
                raise ValueError("Lead not found")

            # 2. Check Business Rule: Idempotency
            if lead.status == "converted":
                raise ValueError("Lead has already been converted")

            # 3. Create Deal (Write 1)
            # We assume the repo handles 'add' but we rely on the final commit here for atomicity
            deal = deal_repo.create(
                tenant_id=tenant_id,
                lead_id=lead.id,
                value_cents=value_cents,
                seller_id=seller_id
            )

            # 4. Update Lead Status (Write 2)
            lead.status = "converted"
            self.db.add(lead)
            
            # 5. Commit Transaction (Atomic)
            # This commits BOTH the new Deal and the Lead update.
            self.db.commit()
            self.db.refresh(deal)
            
            return deal

        except SQLAlchemyError as e:
            # Rollback ensuring no partial state is left (e.g. Deal created but Lead not updated)
            self.db.rollback()
            raise e