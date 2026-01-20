# app/api/finance.py
"""
Module: Finance API Router
Context: Pod B - Public Interface.

Exposes REST endpoints for Invoicing and Payments.
Enforces Authentication and Tenant Isolation.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.authentication.router import get_current_user
from app.models.auth import User
from app.schemas.finance import InvoiceCreate, InvoiceResponse, PaymentCreate, PaymentResponse
from app.services.finance_service import FinanceService

# CLEANED: No prefix/tags. Configuration is in app/api/router.py
router = APIRouter()

# --- DEPENDENCIES ---

def get_service(db: Session = Depends(get_db)) -> FinanceService:
    return FinanceService(db)

# --- ENDPOINTS ---

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    data: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    service: FinanceService = Depends(get_service)
):
    """
    Create a new Invoice with line items.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")
        
    return service.create_invoice(current_user.tenant_id, data)

@router.get("/invoices", response_model=List[InvoiceResponse])
def list_invoices(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    service: FinanceService = Depends(get_service)
):
    """
    List all invoices for the current user's tenant.
    """
    if not current_user.tenant_id:
        return []
    return service.list_invoices(current_user.tenant_id, skip, limit)

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    service: FinanceService = Depends(get_service)
):
    """
    Get specific invoice details (includes Items and Payment History).
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    return service.get_invoice(current_user.tenant_id, invoice_id)

@router.post("/payments", response_model=InvoiceResponse)
def record_payment(
    data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    service: FinanceService = Depends(get_service)
):
    """
    Record a payment against an invoice.
    Returns the updated Invoice object (so UI can see new status/balance).
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")
        
    return service.process_payment(current_user.tenant_id, data)