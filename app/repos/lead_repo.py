# app/repos/lead_repo.py
"""
Module: Lead Repository
Context: Pod B - Data Access Layer

Handles database interactions for the Lead entity.
Enforces tenant isolation on all queries.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.crm import Lead
from app.schemas.crm import LeadCreate

class LeadRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(self, tenant_id: int, owner_id: int, data: LeadCreate) -> Lead:
        """
        Persists a new lead in the database.
        """
        lead = Lead(
            tenant_id=tenant_id,
            owner_id=owner_id,
            name=data.name,
            email=data.email,
            status="new"
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def get(self, lead_id: int, tenant_id: int) -> Optional[Lead]:
        """
        Retrieves a single lead by ID, strictly enforcing tenant ownership.
        """
        return self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id
        ).first()

    def list_all(self, tenant_id: int, limit: int = 100, skip: int = 0) -> List[Lead]:
        """
        Lists leads for a tenant, ordered by newest first.
        """
        return (
            self.db.query(Lead)
            .filter(Lead.tenant_id == tenant_id)
            .order_by(desc(Lead.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_status(self, lead: Lead, new_status: str) -> Lead:
        """
        Updates the status of a lead instance.
        Note: The lead object must already be attached to the session.
        """
        lead.status = new_status
        self.db.commit()
        self.db.refresh(lead)
        return lead