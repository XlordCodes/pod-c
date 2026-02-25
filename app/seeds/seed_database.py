# seed_database.py
import logging
import sys
from datetime import datetime, timezone, timedelta
from app.database import SessionLocal
from app.authentication.hashing import hash_password
from app import models
from app.models.audit import AuditLog
from app.models.crm import Lead, Deal
from app.models.finance import Payment, InvoiceItem, Invoice, LedgerEntry
from app.models.chat import Conversation, ChatMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed():
    """
    Main database seeding function.
    
    Creates Roles, Users, Conversations, and ChatMessages for testing.
    All operations are atomic - any failure triggers a full rollback.
    
    Raises:
        SystemExit: On any error, exits with code 1 after rollback.
    """
    db = SessionLocal()
    try:
        logger.info("Seeding database...")

        # Clear old data to ensure a clean slate
        # We delete in specific order to satisfy Foreign Key constraints
        # Order: ChatMessage -> Conversation -> Payment -> InvoiceItem -> Invoice -> LedgerEntry -> AuditLog -> Deal -> Lead -> Contact -> User -> Role
        logger.info("Clearing existing data...")
        # Chat tables (must be deleted before User due to foreign key constraints)
        db.query(ChatMessage).delete()
        db.query(Conversation).delete()
        # Finance tables (must be deleted before Contact since Invoice references Contact)
        db.query(Payment).delete()
        db.query(InvoiceItem).delete()
        db.query(Invoice).delete()
        db.query(LedgerEntry).delete()
        # Audit and CRM tables
        db.query(AuditLog).delete()
        db.query(Deal).delete()
        db.query(Lead).delete()
        db.query(models.Contact).delete()
        # Auth tables
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
        logger.info("Users seeded successfully!")

        # 3. Seed Conversations and Chat Messages for Analytics Dashboard
        # This data populates the analytics views (sentiment mix, avg response time)
        logger.info("Seeding conversations and chat messages...")
        
        # Create a conversation for tenant_id=1
        # Note: Conversation model only has tenant_id field, no status field
        conversation = Conversation(
            tenant_id=1
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logger.info(f"Created conversation: {conversation.id}")
        
        # Create chat messages with staggered timestamps for analytics
        # Staggering timestamps allows the avg_response view to calculate measurable deltas
        base_time = datetime.now(timezone.utc) - timedelta(hours=2)
        
        messages_data = [
            {
                "text": "I absolutely love this product! It's amazing and works perfectly.",
                "sentiment": "positive",
                "delay_minutes": 0
            },
            {
                "text": "Can you tell me more about the pricing options available?",
                "sentiment": "neutral",
                "delay_minutes": 7
            },
            {
                "text": "I'm having some issues with the delivery, it's very frustrating.",
                "sentiment": "negative",
                "delay_minutes": 15
            },
        ]
        
        for msg_data in messages_data:
            msg_time = base_time + timedelta(minutes=msg_data["delay_minutes"])
            chat_msg = ChatMessage(
                conversation_id=conversation.id,
                text=msg_data["text"],
                sentiment=msg_data["sentiment"],
                created_at=msg_time
            )
            db.add(chat_msg)
            logger.info(f"Created chat message: '{msg_data['text'][:30]}...' [{msg_data['sentiment']}]")
        
        db.commit()
        logger.info("Chat messages seeded successfully!")
        logger.info("Database seeding completed successfully!")

    except Exception as e:
        logger.error(f"An error occurred during seeding: {e}")
        db.rollback()
        raise  # Re-raise the exception to let the caller handle it
    finally:
        db.close()

if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        sys.exit(1)
