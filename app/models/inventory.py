from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    sku = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    price = Column(Numeric(10, 2), nullable=False)
    stock_level = Column(Integer, default=0)
    reorder_point = Column(Integer, default=10)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    transactions = relationship("StockTransaction", back_populates="product")

class StockTransaction(Base):
    """
    Audit log for inventory movements (IN/OUT).
    Never modify stock_level directly without creating a transaction record.
    """
    __tablename__ = "stock_transactions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    change_amount = Column(Integer, nullable=False) # +5 or -5
    reason = Column(String, nullable=False) # "sale", "restock", "damage"
    reference_id = Column(String, nullable=True) # Invoice ID or Order ID
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    product = relationship("Product", back_populates="transactions")