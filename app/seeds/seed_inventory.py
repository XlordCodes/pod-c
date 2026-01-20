# app/seeds/seed_inventory.py
"""
Module: Inventory Seeder
Context: Pod B - Module 6 (Data Fixtures)

Populates the database with realistic demo inventory data.
Uses the InventoryService to ensure all side-effects (Audit Logs, Stock Transactions) 
are triggered correctly, preserving data integrity.
"""

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.inventory_service import InventoryService
from app.schemas.inventory import ProductCreate, StockAdjustment
from app.models.auth import User, Role

# --- Configuration ---
DEMO_TENANT_ID = 1
SEED_DATA = [
    {
        "sku": "LAPTOP-PRO-X1",
        "name": "ProBook X1 (16GB RAM)",
        "description": "High-performance laptop for developers.",
        "price": 1299.99,
        "reorder_point": 5,
        "initial_stock": 50
    },
    {
        "sku": "MOUSE-ERGO-WL",
        "name": "ErgoWireless Mouse",
        "description": "Ergonomic vertical mouse to prevent RSI.",
        "price": 59.99,
        "reorder_point": 20,
        "initial_stock": 200
    },
    {
        "sku": "MONITOR-4K-27",
        "name": "UltraView 4K Monitor 27inch",
        "description": "Color-accurate display for designers.",
        "price": 449.50,
        "reorder_point": 10,
        "initial_stock": 35
    },
    {
        "sku": "KEYBOARD-MECH-RGB",
        "name": "MechMaster RGB Keyboard",
        "description": "Mechanical keyboard with Cherry MX Brown switches.",
        "price": 119.00,
        "reorder_point": 15,
        "initial_stock": 75
    }
]

def get_system_user(db: Session) -> User:
    """
    Retrieves or creates a system admin user to act as the 'actor' for seed operations.
    """
    # 1. Try to find the admin created by seed_database.py
    user = db.query(User).filter(User.email == "admin@ryze.com").first()
    if user:
        return user

    # 2. Fallback: Try generic admin
    user = db.query(User).filter(User.email == "admin@example.com").first()
    if user:
        return user
        
    # 3. Create dummy system user if none exists (Fix: Use 'name', not 'full_name')
    print("Creating temporary system user for seeding...")
    user = User(
        email="admin@example.com",
        hashed_password="hashed_secret", # Dummy hash
        name="System Admin",             # <--- FIXED: Was 'full_name'
        tenant_id=DEMO_TENANT_ID,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def seed_inventory():
    """
    Main execution function.
    """
    db = SessionLocal()
    try:
        print("🌱 Starting Inventory Seed...")
        
        # 1. Setup Context (Service & User)
        service = InventoryService(db)
        user = get_system_user(db)
        
        # 2. Iterate and Create
        for item in SEED_DATA:
            # Check for idempotency (skip if exists)
            existing = service.repo.get_product_by_sku(DEMO_TENANT_ID, item["sku"])
            if existing:
                print(f"   Skipping {item['sku']} (Already exists)")
                continue

            # A. Create Product (Stock starts at 0)
            print(f"   Creating {item['name']}...")
            product_schema = ProductCreate(
                sku=item["sku"],
                name=item["name"],
                description=item["description"],
                price=item["price"],
                reorder_point=item["reorder_point"]
            )
            
            product = service.create_product(
                tenant_id=DEMO_TENANT_ID,
                schema=product_schema,
                user_id=user.id
            )

            # B. Add Initial Stock (Transaction)
            if item["initial_stock"] > 0:
                print(f"   -> Adding initial stock: {item['initial_stock']}")
                service.adjust_stock(
                    tenant_id=DEMO_TENANT_ID,
                    product_id=product.id,
                    adjustment=StockAdjustment(
                        qty=item["initial_stock"],
                        reason="Initial Seeding",
                        reference_id="SEED-001"
                    ),
                    user_id=user.id
                )

        print("✅ Inventory Seeding Complete!")
        
    except Exception as e:
        print(f"❌ Seeding Failed: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_inventory()