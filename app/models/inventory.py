# app/models/inventory.py
"""
Module: Inventory Models
Context: Pod B - Module 5 (Workflow & Inventory)

Defines:
1. Product: Inventory items with current stock state.
2. StockTransaction: Immutable ledger of stock history.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import relationship
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    sku = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Financials (Kept from your version)
    price = Column(Numeric(10, 2), nullable=False, default=0.00)
    
    # Inventory State
    # Renamed 'stock_level' -> 'stock' to match Module 5 specs
    stock = Column(Integer, default=0, nullable=False)
    reorder_point = Column(Integer, default=10)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    transactions = relationship(
        "StockTransaction", 
        back_populates="product", 
        cascade="all, delete-orphan"
    )

class StockTransaction(Base):
    """
    Audit log for inventory movements (IN/OUT).
    Immutable ledger.
    """
    __tablename__ = "stock_transactions"

    id = Column(Integer, primary_key=True, index=True)
    # FIX: Added tenant_id for strict multi-tenant isolation
    tenant_id = Column(Integer, index=True, nullable=False)
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    
    # Renamed 'change_amount' -> 'qty_change' for consistency with Service layer
    qty_change = Column(Integer, nullable=False) # +5 or -5
    
    # Reason: "sale", "restock", "damage", "correction"
    reason = Column(String, nullable=False) 
    
    # Reference: "INV-1001" or "PO-500"
    reference_id = Column(String, nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    product = relationship("Product", back_populates="transactions")