from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.security import encrypt_value, decrypt_value

class Contact(Base):
    """
    Represents an external customer or lead managed by a User.
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True) # Scope data to tenant
    
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True, index=True)
    phone = Column(String, nullable=True, unique=True, index=True)
    
    # --- Extensibility ---
    # Stores dynamic attributes like 'segment', 'source', 'preferences'
    custom_fields = Column(JSON, default={}) 

    # --- Module 5: Encrypted Field ---
    # The database stores the encrypted string in '_national_id'
    _national_id = Column("national_id", String, nullable=True)

    @property
    def national_id(self):
        """Returns the decrypted value when accessed via python."""
        return decrypt_value(self._national_id)

    @national_id.setter
    def national_id(self, value):
        """Encrypts the value automatically when setting."""
        self._national_id = encrypt_value(value)
    
    # Server-side default ensures DB consistency
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    owner_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Relationships
    owner = relationship("app.models.auth.User", back_populates="contacts")
    
    messages = relationship(
        "app.models.chat.Message", 
        back_populates="contact", 
        cascade="all, delete-orphan"
    )

    # New Pod B Relationship
    invoices = relationship(
        "app.models.finance.Invoice",
        back_populates="contact"
    )