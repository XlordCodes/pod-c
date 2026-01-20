# app/services/workflow_service.py
"""
Module: Workflow Service
Context: Pod B - Module 5 (Automation)

Orchestrates cross-domain logic: Finance -> Inventory -> Audit.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.finance import Invoice
from app.services.audit_service import AuditService
from app.repos.inventory_repo import InventoryRepo

class WorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.inventory_repo = InventoryRepo(db)

    def process_invoice_payment(self, tenant_id: int, user_id: int, invoice_id: int):
        """
        Triggered when an Invoice is PAID.
        1. Deducts Stock.
        2. Logs Audit.
        """
        # 1. Fetch Invoice
        # Note: We rely on the relationship 'items' being loaded or available
        invoice = self.db.query(Invoice).filter(
            Invoice.id == invoice_id, 
            Invoice.tenant_id == tenant_id
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # 2. Idempotency Check (Optional but good)
        # In a real app, we check if we already deducted stock for this invoice.
        # For this MVP, we rely on the caller ensuring strict state transitions.

        # 3. Process Inventory
        results = []
        if invoice.items:
            for item in invoice.items:
                # We assume InvoiceItem has a product_id. 
                # If your Finance module stores product_id, use it.
                if hasattr(item, 'product_id') and item.product_id:
                    try:
                        # Deduct stock
                        self.inventory_repo.create_transaction(
                            product_id=item.product_id,
                            change=-(item.quantity), 
                            reason="sale",
                            ref_id=f"INV-{invoice.id}"
                        )
                        results.append(f"Deducted {item.quantity} for Product {item.product_id}")
                    except Exception as e:
                        # Log but continue? Or Fail?
                        # Workflow: fail hard to ensure consistency
                        raise HTTPException(status_code=500, detail=f"Stock error: {str(e)}")

        # 4. Audit Log (Auto-captures Trace ID now)
        self.audit.log_event(
            actor_id=user_id,
            entity="Invoice",
            entity_id=invoice.id,
            action="workflow_payment_processed",
            changes={
                "status": "PAID",
                "workflow": "stock_deduction", 
                "details": results
            }
        )
        
        return {"status": "success", "operations": results}