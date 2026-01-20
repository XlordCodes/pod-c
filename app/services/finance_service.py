# app/services/finance_service.py
"""
Module: Finance Service
Context: Pod B - Business Logic Layer.

Orchestrates the flow of financial data.
Responsible for:
1. Validating business rules (e.g. overpayment checks).
2. Calculating totals.
3. Coordinating atomic updates (Invoice + Payment + Ledger).
"""

import logging
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.finance import InvoiceCreate, PaymentCreate, InvoiceResponse
from app.repos.finance_repo import FinanceRepo
from app.models.finance import Invoice

logger = logging.getLogger(__name__)

class FinanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FinanceRepo(db)

    def create_invoice(self, tenant_id: int, schema: InvoiceCreate) -> Invoice:
        """
        Calculates totals from line items and persists the invoice.
        """
        # 1. Calculate Total Amount
        total = sum(item.quantity * item.unit_price for item in schema.items)
        
        # 2. Persist via Repo
        invoice = self.repo.create_invoice(tenant_id, schema, total)
        
        # 3. Ledger Entry (Debit Accounts Receivable)
        self.repo.add_ledger_entry(
            tenant_id=tenant_id,
            tx_type="debit",
            amount=total,
            description=f"Invoice #{invoice.id} Generated",
            ref_entity="Invoice",
            ref_id=invoice.id
        )
        
        logger.info(f"Created Invoice {invoice.id} for Tenant {tenant_id} (Total: {total})")
        return invoice

    def get_invoice(self, tenant_id: int, invoice_id: int) -> Invoice:
        """
        Retrieves an invoice or raises 404.
        """
        invoice = self.repo.get_invoice(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice

    def list_invoices(self, tenant_id: int, skip: int = 0, limit: int = 100):
        return self.repo.list_invoices(tenant_id, skip, limit)

    def process_payment(self, tenant_id: int, schema: PaymentCreate) -> Invoice:
        """
        Records a payment, updates invoice status, and logs to ledger.
        """
        # 1. Verify Invoice Exists
        invoice = self.repo.get_invoice(schema.invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if invoice.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot pay a cancelled invoice")

        # 2. Record the Payment
        payment = self.repo.record_payment(tenant_id, schema)

        # 3. Calculate New Balance
        # Sum existing payments + this new one
        total_paid = sum(p.amount for p in invoice.payments) # SQLAlchemy verified relationship
        
        # 4. Update Status Logic
        new_status = invoice.status
        if total_paid >= invoice.total_amount:
            new_status = "paid"
        elif total_paid > 0:
            new_status = "partial"
        
        if new_status != invoice.status:
            self.repo.update_status(invoice.id, new_status)

        # 5. Ledger Entry (Credit Cash/Bank)
        self.repo.add_ledger_entry(
            tenant_id=tenant_id,
            tx_type="credit",
            amount=schema.amount,
            description=f"Payment for Invoice #{invoice.id} via {schema.method}",
            ref_entity="Payment",
            ref_id=payment.id
        )

        logger.info(f"Processed Payment {payment.id} for Invoice {invoice.id}. Status: {new_status}")
        
        # Return the updated invoice
        return invoice