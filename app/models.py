from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    from_number = Column(String, index=True)                   
    to_number = Column(String, index=True)                    
    message_id = Column(String, unique=True, index=True)
    payload = Column(JSON)                                     
    text = Column(Text, nullable=True)                         
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    message_type = Column(String, nullable=True)               
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    contact = relationship("Contact", backref="messages")

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

