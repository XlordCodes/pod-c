# seed_database.py
import logging
from app.database import SessionLocal
from app.authentication.hashing import hash_password
from app import models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed():
    db = SessionLocal()
    try:
        logger.info("Seeding database...")

        # Clear old data to ensure a clean slate
        # We delete in specific order to satisfy Foreign Key constraints
        logger.info("Clearing existing data...")
        db.query(models.Contact).delete()
        db.query(models.User).delete()
        db.query(models.Role).delete()
        db.commit()
        logger.info("Old data cleared.")

        # 1. Seed Roles
        # These are the standard roles used for RBAC checks
        roles_to_create = ["admin", "manager", "staff"]
        role_map = {} # Maps role name -> role_id

        for role_name in roles_to_create:
            role = models.Role(name=role_name)
            db.add(role)
            db.commit() 
            db.refresh(role)
            role_map[role_name] = role.id
            logger.info(f"Created role: {role_name}")

        # 2. Seed Users with Roles and Tenants
        # We create a user for each role to facilitate testing
        users_data = [
            {"email": "admin@ryze.com", "name": "Admin User", "role": "admin", "tenant": 1},
            {"email": "manager@ryze.com", "name": "Manager User", "role": "manager", "tenant": 1},
            {"email": "staff@ryze.com", "name": "Staff User", "role": "staff", "tenant": 1},
            # A user in a different tenant to test isolation later
            {"email": "tenant2@ryze.com", "name": "Tenant 2 Admin", "role": "admin", "tenant": 2},
        ]

        hashed_pass = hash_password("pass123") # Default password for all seed users

        for u_data in users_data:
            user = models.User(
                email=u_data["email"],
                name=u_data["name"],
                hashed_password=hashed_pass,
                role_id=role_map[u_data["role"]],
                tenant_id=u_data["tenant"]
            )
            db.add(user)
            logger.info(f"Created user: {user.email} [Role: {u_data['role']}, Tenant: {u_data['tenant']}]")
        
        db.commit()
        logger.info("Database seeding completed successfully!")

    except Exception as e:
        logger.error(f"An error occurred during seeding: {e}")
        db.rollback() # Roll back in case of error
    finally:
        db.close()

if __name__ == "__main__":
    seed()