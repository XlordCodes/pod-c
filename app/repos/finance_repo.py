# app/repos/finance_repo.py
"""
Module: Finance Repository
Context: Pod B - Data Access Layer.

Handles database interactions for Invoices, Payments, and Ledger Entries.
Isolates SQL logic from business rules.
"""

import logging
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from sqlalchemy.dialects import sqlite

from app.models.finance import Invoice, InvoiceItem, Payment, LedgerEntry
from app.schemas.finance import InvoiceCreate, PaymentCreate

logger = logging.getLogger(__name__)

class FinanceRepo:
    """
    Repository for managing Finance data.
    """
    def __init__(self, db: Session):
        self.db = db
        # Detect if we're using SQLite (for test compatibility)
        # SQLite doesn't support SELECT FOR UPDATE properly
        self._is_sqlite = "sqlite" in self.db.bind.dialect.name.lower()
    def create_invoice(self, tenant_id: int, schema: InvoiceCreate, total_amount: Decimal) -> Invoice:
        """
        Creates an Invoice and its Line Items.
        
        Args:
            tenant_id (int): Context tenant.
            schema (InvoiceCreate): Validated request data.
            total_amount (Decimal): Pre-calculated total from Service layer.
            
        Returns:
            Invoice: The created invoice with items attached.
            
        Note: Does NOT commit. Uses flush() to generate IDs.
        """
        # 1. Create the parent Invoice
        db_invoice = Invoice(
            tenant_id=tenant_id,
            contact_id=schema.contact_id,
            total_amount=total_amount,
            currency=schema.currency,
            due_date=schema.due_date,
            status="draft"
        )
        self.db.add(db_invoice)
        
        # [CRITICAL] Flush to generate db_invoice.id for the items
        self.db.flush() 

        # 2. Create the child Items
        for item in schema.items:
            db_item = InvoiceItem(
                invoice_id=db_invoice.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price
            )
            self.db.add(db_item)

        # No commit here. Service layer must handle the transaction boundary.
        return db_invoice

    def get_invoice(self, invoice_id: int, tenant_id: int) -> Optional[Invoice]:
        """
        Fetches a single invoice with items and payments loaded eagerly.
        Ensures tenant isolation.
        """
        return (
            self.db.query(Invoice)
            .options(joinedload(Invoice.items), joinedload(Invoice.payments))
            .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
            .first()
        )
    
    def get_invoice_for_update(self, invoice_id: int, tenant_id: int) -> Optional[Invoice]:
        """
        Fetches an invoice with a pessimistic lock (SELECT FOR UPDATE).
        Prevents concurrent modifications during payment processing.
        
        CRITICAL SECURITY: This blocks other transactions from reading/writing this row
        until the current transaction commits or rolls back. This prevents race conditions
        where multiple concurrent payments could be processed for the same invoice.
        
        SQLITE COMPATIBILITY: SQLite doesn't support FOR UPDATE properly in all cases.
        We skip the lock for SQLite (tests), but keep it for PostgreSQL (production).
        
        Args:
            invoice_id: The invoice ID to lock
            tenant_id: Tenant ID for isolation
            
        Returns:
            Invoice with row-level lock (PostgreSQL) or without lock (SQLite), or None if not found
        """
        query = (
            self.db.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        )
        
        # Only apply FOR UPDATE for PostgreSQL (not supported in SQLite tests)
        if not self._is_sqlite:
            query = query.with_for_update()
        else:
            logger.debug(f"SQLite detected: skipping FOR UPDATE lock for invoice {invoice_id}")
        
        invoice = query.first()
        
        # If found, we can explicitly load relationships if needed, 
        # but usually the Service layer accesses them which triggers lazy loading.
        # This is safe because the parent Invoice row is now locked.
        return invoice

    def list_invoices(self, tenant_id: int, skip: int = 0, limit: int = 100) -> List[Invoice]:
        """
        Lists invoices for a specific tenant, ordered by newest first.
        """
        return (
            self.db.query(Invoice)
            .filter(Invoice.tenant_id == tenant_id)
            .order_by(desc(Invoice.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def record_payment(self, tenant_id: int, schema: PaymentCreate) -> Payment:
        """
        Records a payment against an invoice.
        Does NOT update invoice status (Service layer handles that).
        """
        payment = Payment(
            tenant_id=tenant_id,
            invoice_id=schema.invoice_id,
            amount=schema.amount,
            method=schema.method,
            reference_id=schema.reference_id
        )
        self.db.add(payment)
        self.db.flush() # Generate ID
        return payment

    def update_status(self, invoice_id: int, tenant_id: int, new_status: str) -> Optional[Invoice]:
        """
        Updates the status of an invoice (e.g., 'draft' -> 'paid').
        Enforces tenant isolation to prevent cross-tenant status manipulation.
        
        Args:
            invoice_id: The invoice ID to update
            tenant_id: Tenant ID for security isolation
            new_status: New status value (e.g., 'paid', 'partial', 'cancelled')
            
        Returns:
            Updated invoice or None if not found
        """
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
            .first()
        )
        if invoice:
            invoice.status = new_status
            self.db.flush() # Persist change to session, but don't commit yet
        return invoice

    def add_ledger_entry(self, 
                         tenant_id: int, 
                         tx_type: str, 
                         amount: Decimal, 
                         description: str,
                         ref_entity: str = None,
                         ref_id: int = None) -> LedgerEntry:
        """
        Creates an immutable ledger entry for audit and accounting.
        """
        entry = LedgerEntry(
            tenant_id=tenant_id,
            transaction_type=tx_type,
            amount=amount,
            description=description,
            reference_entity=ref_entity,
            reference_id=ref_id
        )
        self.db.add(entry)
        self.db.flush()
        return entry