# app/api/finance.py
"""
Module: Finance API Router
Context: Pod B - Business Logic.

Exposes REST endpoints for Invoicing and Payments.
Delegates logic to FinanceService (Double-Entry Bookkeeping).
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

# --- Core Imports ---
from app.database import get_db
from app.models.auth import User
from app.authentication.router import get_current_user

# --- Domain Imports ---
# FIX: Use InvoiceResponse to match your actual schema file
from app.schemas.finance import InvoiceCreate, InvoiceResponse, PaymentCreate
from app.services.finance_service import FinanceService

# Initialize Router
router = APIRouter()

# --- Dependency Injection ---

def get_service(db: Session = Depends(get_db)) -> FinanceService:
    """
    Factory to create FinanceService with current DB session.
    """
    return FinanceService(db)

# --- Endpoints ---

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice_in: InvoiceCreate,
    service: FinanceService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Create an Invoice (and automatically create the Ledger Entry).
    """
    if not current_user.tenant_id:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST, 
             detail="User has no tenant."
         )

    return service.create_invoice(
        tenant_id=current_user.tenant_id, 
        schema=invoice_in
    )

@router.get("/invoices", response_model=List[InvoiceResponse])
def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: FinanceService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    List all invoices for the authenticated user's tenant.
    """
    if not current_user.tenant_id:
        return []
        
    return service.list_invoices(current_user.tenant_id, skip, limit)

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    service: FinanceService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific invoice with its line items and payment history.
    """
    if not current_user.tenant_id:
         raise HTTPException(status_code=400, detail="User has no tenant.")
         
    return service.get_invoice(current_user.tenant_id, invoice_id)

@router.post("/payments", response_model=InvoiceResponse)
def record_payment(
    payment_in: PaymentCreate,
    service: FinanceService = Depends(get_service),
    current_user: User = Depends(get_current_user)
):
    """
    Record a Payment against an Invoice.
    
    - Updates Invoice status (Partial/Paid).
    - Creates a Ledger Entry (Credit Cash).
    - Returns the updated Invoice.
    """
    if not current_user.tenant_id:
         raise HTTPException(status_code=400, detail="User has no tenant.")

    try:
        return service.process_payment(
            tenant_id=current_user.tenant_id, 
            schema=payment_in
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        # Catch unexpected errors to prevent 500 crashes without context
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Payment processing failed."
        )