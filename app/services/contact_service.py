# app/services/contact_service.py
"""
Module: Contact Service
Context: Pod A - CRM Core

Handles business logic for Contact management, including:
1. CRUD operations
2. Multi-tenant data isolation
3. Caching (Read-through / Write-invalidate)
"""

import json
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.crm import Contact
from app.schemas.crm import ContactCreate, ContactUpdate, ContactOut
from app.core.cache import get_cache, set_cache, invalidate_cache

class ContactService:
    def __init__(self, db: Session):
        self.db = db

    async def create_contact(self, tenant_id: int, owner_id: int, data: ContactCreate) -> Contact:
        """
        Creates a new contact and invalidates the list cache.
        """
        db_contact = Contact(
            tenant_id=tenant_id,
            owner_id=owner_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            custom_fields=data.custom_fields
        )
        
        try:
            self.db.add(db_contact)
            self.db.commit()
            self.db.refresh(db_contact)
            
            # Invalidate owner's contact list cache so the UI sees the new contact immediately
            await invalidate_cache(f"contacts:{owner_id}:*")
            return db_contact
            
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Contact with this phone or email already exists.")

    async def list_contacts(self, owner_id: int, skip: int = 0, limit: int = 100) -> List[ContactOut]:
        """
        Fetches contacts with Read-Through Caching.
        """
        cache_key = f"contacts:{owner_id}:{skip}:{limit}"
        
        # 1. Try Cache
        cached_data = await get_cache(cache_key)
        if cached_data:
            # Redis returns a JSON string (or list of dicts depending on implementation).
            # We must convert these raw dicts back into Pydantic models (ContactOut).
            if isinstance(cached_data, str):
                 cached_data = json.loads(cached_data)
            
            return [ContactOut.model_validate(item) for item in cached_data]

        # 2. Query DB
        contacts = (
            self.db.query(Contact)
            .filter(Contact.owner_id == owner_id)
            .order_by(Contact.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # 3. Set Cache
        # We must serialize the SQLAlchemy objects to JSON-compatible dicts
        serialized_contacts = [
            ContactOut.model_validate(c).model_dump(mode='json') 
            for c in contacts
        ]
        
        # Store in Redis (expires in 60 seconds to keep data relatively fresh)
        await set_cache(cache_key, serialized_contacts, expire=60)
        
        # Return the ORM objects (FastAPI will serialize them to JSON automatically)
        return contacts 

    async def get_contact(self, contact_id: int, owner_id: int) -> Contact:
        """
        Fetches a single contact. 
        Note: We generally don't cache individual item lookups unless high traffic.
        """
        contact = self.db.query(Contact).filter(
            Contact.id == contact_id, 
            Contact.owner_id == owner_id
        ).first()
        
        if not contact:
            raise ValueError("Contact not found")
            
        return contact

    async def update_contact(self, contact_id: int, owner_id: int, data: ContactUpdate) -> Contact:
        """
        Updates a contact and invalidates cache.
        """
        # Fetch first to ensure ownership
        contact = await self.get_contact(contact_id, owner_id)
        
        # Update fields dynamically
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(contact, key, value)
            
        try:
            self.db.commit()
            self.db.refresh(contact)
            
            # Invalidate cache so the list reflects the changes
            await invalidate_cache(f"contacts:{owner_id}:*")
            return contact
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Update conflict: Email/Phone already in use.")

    async def delete_contact(self, contact_id: int, owner_id: int):
        """
        Deletes a contact and invalidates cache.
        """
        contact = await self.get_contact(contact_id, owner_id)
        
        self.db.delete(contact)
        self.db.commit()
        
        # Invalidate cache
        await invalidate_cache(f"contacts:{owner_id}:*")