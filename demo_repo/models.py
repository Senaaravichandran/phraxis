"""
Database models for the payment service.
Defines User and Payment entities with SQLAlchemy ORM.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class UserTier(enum.Enum):
    """User subscription tier enumeration."""
    FREE = "free"
    PREMIUM = "premium"


class PaymentStatus(enum.Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class User(Base):
    """
    User model representing a customer in the payment system.
    
    Attributes:
        id: Unique user identifier
        email: User's email address (unique)
        tier: Subscription tier (free or premium)
        created_at: Account creation timestamp
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    tier = Column(Enum(UserTier), default=UserTier.FREE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to payments
    payments = relationship('Payment', back_populates='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', tier='{self.tier.value}')>"
    
    def to_dict(self):
        """Convert user to dictionary representation."""
        return {
            'id': self.id,
            'email': self.email,
            'tier': self.tier.value,
            'created_at': self.created_at.isoformat()
        }


class Payment(Base):
    """
    Payment model representing a financial transaction.
    
    Attributes:
        id: Unique payment identifier
        user_id: Foreign key to User
        amount: Payment amount in USD
        status: Current payment status
        card_token: Tokenized card information (for security)
        created_at: Transaction timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    card_token = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to user
    user = relationship('User', back_populates='payments')
    
    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status='{self.status.value}')>"
    
    def to_dict(self):
        """Convert payment to dictionary representation."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# Made with Bob
