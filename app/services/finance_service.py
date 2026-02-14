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
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.finance import InvoiceCreate, PaymentCreate
from app.repos.finance_repo import FinanceRepo
from app.models.finance import Invoice

logger = logging.getLogger(__name__)

class FinanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FinanceRepo(db)

    def create_invoice(self, tenant_id: int, schema: InvoiceCreate) -> Invoice:
        """
        Calculates totals and persists the invoice + ledger entry atomically.
        """
        # 1. Calculate Total Amount
        # We compute this on the backend to prevent frontend tampering
        # CRITICAL: Use Decimal("0") as start to prevent float arithmetic
        total = sum(
            (Decimal(str(item.quantity)) * item.unit_price for item in schema.items),
            start=Decimal("0")
        )
        
        try:
            # 2. Persist Invoice (Flush only, ID generated)
            invoice = self.repo.create_invoice(tenant_id, schema, total)
            
            # 3. Ledger Entry (Debit Accounts Receivable) - Flush only
            # Tracks that money is owed to the business
            self.repo.add_ledger_entry(
                tenant_id=tenant_id,
                tx_type="debit",
                amount=total,
                description=f"Invoice #{invoice.id} Generated",
                ref_entity="Invoice",
                ref_id=invoice.id
            )
            
            # 4. Atomic Commit
            # Both the Invoice and the Ledger entry are saved together.
            self.db.commit()
            self.db.refresh(invoice)
            
            logger.info(f"Created Invoice {invoice.id} for Tenant {tenant_id} (Total: {total})")
            return invoice

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating invoice: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transaction failed")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating invoice: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="System error")

    def get_invoice(self, tenant_id: int, invoice_id: int) -> Invoice:
        """
        Retrieves an invoice or raises 404.
        """
        invoice = self.repo.get_invoice(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice

    def list_invoices(self, tenant_id: int, skip: int = 0, limit: int = 100) -> List[Invoice]:
        return self.repo.list_invoices(tenant_id, skip, limit)

    def process_payment(self, tenant_id: int, schema: PaymentCreate) -> Invoice:
        """
        Records a payment, updates invoice status, and logs to ledger.
        Atomic operation with row-level locking to prevent race conditions.
        
        SECURITY FEATURES:
        - Pessimistic locking (SELECT FOR UPDATE) prevents concurrent payment processing
        - Overpayment validation prevents collecting more than owed
        - Decimal arithmetic prevents floating-point rounding errors
        """
        try:
            # 1. Verify Invoice Exists (WITH ROW LOCK)
            # CRITICAL: Use get_invoice_for_update to prevent race conditions
            invoice = self.repo.get_invoice_for_update(schema.invoice_id, tenant_id)
            if not invoice:
                raise HTTPException(status_code=404, detail="Invoice not found")

            if invoice.status == "cancelled":
                raise HTTPException(status_code=400, detail="Cannot pay a cancelled invoice")

            # 2. Calculate Current Balance (BEFORE new payment)
            # CRITICAL: Use Decimal arithmetic to prevent float errors
            previous_paid = sum(
                (Decimal(str(p.amount)) for p in invoice.payments),
                start=Decimal("0")
            )
            remaining_balance = Decimal(str(invoice.total_amount)) - previous_paid
            
            # 3. Overpayment Validation
            # CRITICAL: Prevent collecting more than owed
            payment_amount = Decimal(str(schema.amount))
            if payment_amount > remaining_balance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payment amount {schema.amount} exceeds remaining balance {remaining_balance}"
                )

            # 4. Record the Payment (Flush only)
            payment = self.repo.record_payment(tenant_id, schema)

            # 5. Calculate New Total Paid
            total_paid = previous_paid + schema.amount
            
            # 6. Update Status Logic
            new_status = invoice.status
            if total_paid >= Decimal(str(invoice.total_amount)):
                new_status = "paid"
            elif total_paid > 0:
                new_status = "partial"
            
            if new_status != invoice.status:
                self.repo.update_status(invoice.id, tenant_id, new_status)

            # 5. Ledger Entry (Credit Cash/Bank) - Flush only
            # Tracks that money has been received
            self.repo.add_ledger_entry(
                tenant_id=tenant_id,
                tx_type="credit",
                amount=schema.amount,
                description=f"Payment for Invoice #{invoice.id} via {schema.method}",
                ref_entity="Payment",
                ref_id=payment.id
            )

            # 6. Atomic Commit
            self.db.commit()
            
            # Refresh invoice to return latest state (including the new payment status)
            self.db.refresh(invoice)
            
            logger.info(f"Processed Payment {payment.id} for Invoice {invoice.id}. Status: {new_status}")
            return invoice

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error processing payment: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transaction failed")
        except HTTPException as e:
            # CRITICAL: Re-raise HTTPExceptions (like overpayment errors) without wrapping them
            # This ensures 400 errors are returned correctly instead of becoming 500
            self.db.rollback()
            logger.info(f"Payment validation failed: {e.detail}")
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error processing payment: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="System error")