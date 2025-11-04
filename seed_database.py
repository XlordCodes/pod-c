# seed_database.py
import logging
from app.database import SessionLocal
from app.authentication import crud as auth_crud
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
        logger.info("Deleting existing contacts and users...")
        db.query(models.Contact).delete()
        db.query(models.User).delete()
        db.commit()
        logger.info("Old data cleared.")

        # Insert fresh user data with hashed passwords
        users_to_create = []
        for i in range(1, 6):
            email = f"user{i}@example.com"
            # Check if user already exists
            user = auth_crud.get_user_by_email(db, email=email)
            if not user:
                hashed_pass = hash_password("pass123") # Securely hash the password
                user = auth_crud.create_user(
                    db,
                    name=f"User{i}",
                    email=email,
                    hashed_password=hashed_pass
                )
                users_to_create.append(user)
                logger.info(f"Created user: {user.email}")
            else:
                logger.info(f"User {user.email} already exists.")
        
        # NOTE: Contact seeding logic can be added here once contact CRUD is merged.

        logger.info("Database seeding completed successfully!")

    except Exception as e:
        logger.error(f"An error occurred during seeding: {e}")
        db.rollback() # Roll back in case of error
    finally:
        db.close()

if __name__ == "__main__":
    seed()
