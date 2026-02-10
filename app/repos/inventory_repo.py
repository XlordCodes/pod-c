# app/repos/inventory_repo.py
"""
Module: Inventory Repository
Context: Pod B - Module 5 (Workflow & Inventory)

Handles persistence for Products and Stock Transactions.
Enforces strict multi-tenancy and atomic stock updates.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.inventory import Product, StockTransaction
from app.schemas.inventory import ProductCreate

class InventoryRepo:
    """
    Repository for managing Inventory data.
    """
    def __init__(self, db: Session):
        self.db = db

    def create_product(self, tenant_id: int, schema: ProductCreate) -> Product:
        """
        Creates a new product catalog entry.
        
        Args:
            tenant_id (int): The organization context.
            schema (ProductCreate): Validated request data.
            
        Returns:
            Product: The created product entity.
        """
        product = Product(
            tenant_id=tenant_id,
            sku=schema.sku,
            name=schema.name,
            description=schema.description,
            price=schema.price,
            stock=0, # Always start at 0. Use transaction to add initial stock.
            reorder_point=schema.reorder_point
        )
        self.db.add(product)
        
        # Using flush ensures the ID is generated for downstream use (like Audit logs) 
        # while keeping the transaction open.
        self.db.flush() 
        return product

    def get_product(self, tenant_id: int, product_id: int) -> Optional[Product]:
        """
        Retrieves a single product by ID, scoped to the tenant.
        """
        return (
            self.db.query(Product)
            .filter(Product.id == product_id, Product.tenant_id == tenant_id)
            .first()
        )

    def get_product_for_update(self, tenant_id: int, product_id: int) -> Optional[Product]:
        """
        Retrieves and LOCKS a product row for atomic updates.
        
        Uses 'SELECT ... FOR UPDATE' to prevent race conditions.
        If another transaction holds the lock, this will wait until it releases.
        
        Args:
            tenant_id (int): Context tenant.
            product_id (int): Product to lock.
            
        Returns:
            Optional[Product]: The locked product instance.
        """
        return (
            self.db.query(Product)
            .filter(Product.id == product_id, Product.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
    
    def get_product_by_sku(self, tenant_id: int, sku: str) -> Optional[Product]:
        """
        Retrieves a product by SKU, scoped to the tenant.
        """
        return (
            self.db.query(Product)
            .filter(Product.sku == sku, Product.tenant_id == tenant_id)
            .first()
        )

    def list_products(self, tenant_id: int, skip: int = 0, limit: int = 100) -> List[Product]:
        """
        Lists products for the tenant with pagination.
        """
        return (
            self.db.query(Product)
            .filter(Product.tenant_id == tenant_id)
            .order_by(Product.name)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_transaction(
        self, 
        product: Product, 
        change: int, 
        reason: str, 
        ref_id: Optional[str] = None
    ) -> StockTransaction:
        """
        Records the transaction AND updates the product stock level atomically.
        
        Args:
            product (Product): The product object (must be attached to session).
            change (int): The quantity to add (positive) or remove (negative).
            reason (str): Description of the movement (e.g., 'sale', 'restock').
            ref_id (Optional[str]): External reference ID (e.g., Invoice #123).
            
        Returns:
            StockTransaction: The created audit record.
        """
        # 1. Create Audit Record
        txn = StockTransaction(
            tenant_id=product.tenant_id,
            product_id=product.id,
            qty_change=change,  # Updated field name
            reason=reason,
            reference_id=ref_id # Updated field name
        )
        self.db.add(txn)
        
        # 2. Update Stock Level on the Product Model
        # This acts as a cache/snapshot for fast reads.
        # Note: The 'product' row MUST be locked via get_product_for_update() 
        # before calling this to ensure safety.
        product.stock += change
        
        # The Service layer must commit the transaction.
        self.db.flush()
        return txn