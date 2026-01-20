# app/api/inventory.py
"""
Module: Inventory API
Context: Pod B - Module 5 (Public Interface).

Exposes endpoints for Product Catalog and Stock Management.
Integrated with RBAC (Module 4) to ensure only authorized staff can modify inventory.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.authentication.router import get_current_user
from app.models.auth import User
from app.schemas.inventory import ProductCreate, ProductResponse, StockAdjustment
from app.services.inventory_service import InventoryService
from app.core.permissions import require_role  # Module 4 Integration

router = APIRouter()

# --- DEPENDENCIES ---

def get_service(db: Session = Depends(get_db)) -> InventoryService:
    """
    Dependency to instantiate the Inventory Service.
    """
    return InventoryService(db)

# --- ENDPOINTS ---

@router.post(
    "/products", 
    response_model=ProductResponse, 
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(["admin", "manager"]))]
)
def create_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    service: InventoryService = Depends(get_service)
):
    """
    Create a new product in the catalog.
    
    Permissions:
    - Admin or Manager only.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User is not associated with a tenant"
        )
        
    # Pass user_id to service for Audit Logging
    return service.create_product(
        tenant_id=current_user.tenant_id, 
        schema=data, 
        user_id=current_user.id
    )

@router.get("/products", response_model=List[ProductResponse])
def list_products(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    service: InventoryService = Depends(get_service)
):
    """
    List all products in the catalog.
    
    Permissions:
    - Open to all authenticated users in the tenant.
    """
    if not current_user.tenant_id:
        return []
        
    return service.list_products(current_user.tenant_id, skip, limit)

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    service: InventoryService = Depends(get_service)
):
    """
    Get details for a single product.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Product not found"
        )
        
    return service.get_product(current_user.tenant_id, product_id)

@router.post(
    "/products/{product_id}/adjust", 
    response_model=ProductResponse,
    dependencies=[Depends(require_role(["admin", "manager"]))]
)
def adjust_stock(
    product_id: int,
    data: StockAdjustment,
    current_user: User = Depends(get_current_user),
    service: InventoryService = Depends(get_service)
):
    """
    Manually adjust stock levels (e.g., Restock, Damage, Correction).
    
    Payload Example: 
    - {"qty": 10, "reason": "restock"}
    - {"qty": -2, "reason": "damage"}
    
    Permissions:
    - Admin or Manager only.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User is not associated with a tenant"
        )
        
    # Pass user_id to service for Audit Logging
    return service.adjust_stock(
        tenant_id=current_user.tenant_id, 
        product_id=product_id, 
        adjustment=data,
        user_id=current_user.id
    )