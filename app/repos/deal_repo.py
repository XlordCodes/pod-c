# app/repos/deal_repo.py
"""
Module: Deal Repository
Context: Pod B - Data Access Layer.

Responsible for the persistence and retrieval of Deal entities.
Enforces tenant isolation on all database queries to prevent data leakage.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.crm import Deal

class DealRepo:
    """
    Repository for managing Deal entities.
    Abstracts raw DB operations from the Service layer.
    """
    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.
        
        Args:
            db (Session): The active SQLAlchemy database session.
        """
        self.db = db

    def create(self, tenant_id: int, lead_id: int, value_cents: int, seller_id: Optional[int] = None) -> Deal:
        """
        Creates a new Deal record linked to a specific Lead.
        
        Args:
            tenant_id (int): The tenant context for this data.
            lead_id (int): The ID of the lead being converted.
            value_cents (int): The monetary value of the deal in cents.
            seller_id (Optional[int]): The ID of the user (salesperson) owning this deal.
            
        Returns:
            Deal: The newly created and persisted Deal object.
        """
        deal = Deal(
            tenant_id=tenant_id,
            lead_id=lead_id,
            value_cents=value_cents,
            seller_id=seller_id
        )
        self.db.add(deal)
        self.db.commit()
        self.db.refresh(deal)
        return deal

    def get(self, deal_id: int, tenant_id: int) -> Optional[Deal]:
        """
        Retrieves a single deal by ID, strictly enforcing tenant ownership.
        
        Args:
            deal_id (int): The primary key of the deal.
            tenant_id (int): The tenant ID to filter by.
            
        Returns:
            Optional[Deal]: The deal object if found, otherwise None.
        """
        return self.db.query(Deal).filter(
            Deal.id == deal_id, 
            Deal.tenant_id == tenant_id
        ).first()

    def list_all(self, tenant_id: int, limit: int = 100, skip: int = 0) -> List[Deal]:
        """
        Lists deals for a specific tenant, ordered by creation date (newest first).
        
        Args:
            tenant_id (int): The tenant ID to filter by.
            limit (int): Maximum number of records to return.
            skip (int): Number of records to skip (pagination).
            
        Returns:
            List[Deal]: A list of deal objects.
        """
        return (
            self.db.query(Deal)
            .filter(Deal.tenant_id == tenant_id)
            .order_by(desc(Deal.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )