"""
Payment service handling all payment-related business logic.
Processes charges, refunds, and payment queries with proper error handling.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models import Payment, User, PaymentStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaymentServiceError(Exception):
    """Base exception for payment service errors."""
    pass


class InvalidAmountError(PaymentServiceError):
    """Raised when payment amount is invalid."""
    pass


class InvalidCardError(PaymentServiceError):
    """Raised when card token is invalid."""
    pass


class PaymentNotFoundError(PaymentServiceError):
    """Raised when payment record is not found."""
    pass


class UserNotFoundError(PaymentServiceError):
    """Raised when user is not found."""
    pass


class RefundError(PaymentServiceError):
    """Raised when refund operation fails."""
    pass


class PaymentService:
    """
    Service class for handling payment operations.
    Provides methods for processing payments, refunds, and queries.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize payment service with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    def process(self, user_id: int, amount: float, card_token: str) -> Dict[str, Any]:
        """
        Process a payment transaction.
        
        Args:
            user_id: ID of the user making the payment
            amount: Payment amount in USD
            card_token: Tokenized card information
        
        Returns:
            Dictionary containing payment details
        
        Raises:
            InvalidAmountError: If amount is invalid
            InvalidCardError: If card token is invalid
            UserNotFoundError: If user does not exist
            PaymentServiceError: If payment processing fails
        """
        logger.info(f"Processing payment for user {user_id}, amount: ${amount}")
        
        # Validate amount
        if amount <= 0:
            logger.error(f"Invalid amount: {amount}")
            raise InvalidAmountError(f"Payment amount must be greater than 0, got {amount}")
        
        if amount > 10000:
            logger.error(f"Amount exceeds maximum: {amount}")
            raise InvalidAmountError(f"Payment amount cannot exceed $10,000, got ${amount}")
        
        # Validate card token
        if not card_token or len(card_token) < 10:
            logger.error("Invalid card token provided")
            raise InvalidCardError("Invalid card token format")
        
        try:
            # Verify user exists
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User not found: {user_id}")
                raise UserNotFoundError(f"User with ID {user_id} not found")
            
            # Create payment record
            payment = Payment(
                user_id=user_id,
                amount=amount,
                card_token=card_token,
                status=PaymentStatus.PENDING
            )
            
            self.db.add(payment)
            self.db.flush()
            
            # Simulate payment processing
            # In production, this would call a payment gateway API
            payment_successful = self._process_with_gateway(card_token, amount)
            
            if payment_successful:
                payment.status = PaymentStatus.COMPLETED
                logger.info(f"Payment {payment.id} completed successfully")
            else:
                payment.status = PaymentStatus.FAILED
                logger.warning(f"Payment {payment.id} failed")
            
            self.db.commit()
            
            return {
                'payment_id': payment.id,
                'user_id': payment.user_id,
                'amount': payment.amount,
                'status': payment.status.value,
                'created_at': payment.created_at.isoformat()
            }
            
        except (InvalidAmountError, InvalidCardError, UserNotFoundError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during payment processing: {e}")
            raise PaymentServiceError(f"Failed to process payment: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during payment processing: {e}")
            raise PaymentServiceError(f"Unexpected error: {str(e)}")
    
    def _process_with_gateway(self, card_token: str, amount: float) -> bool:
        """
        Simulate payment gateway processing.
        In production, this would integrate with Stripe, PayPal, etc.
        
        Args:
            card_token: Tokenized card information
            amount: Payment amount
        
        Returns:
            True if payment successful, False otherwise
        """
        # Simulate gateway logic
        # Fail if card token starts with "invalid"
        if card_token.startswith("invalid"):
            return False
        
        # Simulate 95% success rate
        import random
        return random.random() > 0.05
    
    def refund(self, payment_id: int) -> Dict[str, Any]:
        """
        Process a refund for a completed payment.
        
        Args:
            payment_id: ID of the payment to refund
        
        Returns:
            Dictionary containing refund details
        
        Raises:
            PaymentNotFoundError: If payment does not exist
            RefundError: If refund cannot be processed
        """
        logger.info(f"Processing refund for payment {payment_id}")
        
        try:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            
            if not payment:
                logger.error(f"Payment not found: {payment_id}")
                raise PaymentNotFoundError(f"Payment with ID {payment_id} not found")
            
            if payment.status == PaymentStatus.REFUNDED:
                logger.error(f"Payment {payment_id} already refunded")
                raise RefundError(f"Payment {payment_id} has already been refunded")
            
            if payment.status != PaymentStatus.COMPLETED:
                logger.error(f"Cannot refund payment {payment_id} with status {payment.status.value}")
                raise RefundError(f"Can only refund completed payments, current status: {payment.status.value}")
            
            # Process refund
            payment.status = PaymentStatus.REFUNDED
            payment.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Refund processed successfully for payment {payment_id}")
            
            return {
                'payment_id': payment.id,
                'amount': payment.amount,
                'status': payment.status.value,
                'refunded_at': payment.updated_at.isoformat()
            }
            
        except (PaymentNotFoundError, RefundError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during refund: {e}")
            raise RefundError(f"Failed to process refund: {str(e)}")
    
    def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a payment record by ID.
        
        Args:
            payment_id: ID of the payment to retrieve
        
        Returns:
            Payment details dictionary or None if not found
        """
        logger.info(f"Retrieving payment {payment_id}")
        
        try:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            
            if not payment:
                logger.warning(f"Payment {payment_id} not found")
                return None
            
            return payment.to_dict()
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving payment: {e}")
            raise PaymentServiceError(f"Failed to retrieve payment: {str(e)}")
    
    def list_user_payments(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all payments for a specific user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of payments to return (default: 50)
        
        Returns:
            List of payment dictionaries
        
        Raises:
            UserNotFoundError: If user does not exist
        """
        logger.info(f"Listing payments for user {user_id}")
        
        try:
            # Verify user exists
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User not found: {user_id}")
                raise UserNotFoundError(f"User with ID {user_id} not found")
            
            payments = self.db.query(Payment)\
                .filter(Payment.user_id == user_id)\
                .order_by(Payment.created_at.desc())\
                .limit(limit)\
                .all()
            
            logger.info(f"Found {len(payments)} payments for user {user_id}")
            
            return [payment.to_dict() for payment in payments]
            
        except UserNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error listing payments: {e}")
            raise PaymentServiceError(f"Failed to list payments: {str(e)}")

# Made with Bob
