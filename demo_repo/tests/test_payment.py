"""
Pytest tests for PaymentService.
Tests cover successful operations, error cases, and edge conditions.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, Payment, UserTier, PaymentStatus
from services.payment_service import (
    PaymentService,
    InvalidAmountError,
    InvalidCardError,
    PaymentNotFoundError,
    UserNotFoundError,
    RefundError
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(email='test@example.com', tier=UserTier.FREE)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def payment_service(db_session):
    """Create a PaymentService instance."""
    return PaymentService(db_session)


def test_successful_payment(payment_service, test_user):
    """Test successful payment processing."""
    result = payment_service.process(
        user_id=test_user.id,
        amount=99.99,
        card_token='tok_visa_4242424242424242'
    )
    
    assert result['payment_id'] is not None
    assert result['user_id'] == test_user.id
    assert result['amount'] == 99.99
    assert result['status'] in ['completed', 'failed']
    assert 'created_at' in result


def test_invalid_amount_zero(payment_service, test_user):
    """Test payment with zero amount raises error."""
    with pytest.raises(InvalidAmountError) as exc_info:
        payment_service.process(
            user_id=test_user.id,
            amount=0,
            card_token='tok_visa_4242424242424242'
        )
    
    assert 'must be greater than 0' in str(exc_info.value)


def test_invalid_amount_negative(payment_service, test_user):
    """Test payment with negative amount raises error."""
    with pytest.raises(InvalidAmountError) as exc_info:
        payment_service.process(
            user_id=test_user.id,
            amount=-50.00,
            card_token='tok_visa_4242424242424242'
        )
    
    assert 'must be greater than 0' in str(exc_info.value)


def test_invalid_card_token(payment_service, test_user):
    """Test payment with invalid card token raises error."""
    with pytest.raises(InvalidCardError) as exc_info:
        payment_service.process(
            user_id=test_user.id,
            amount=99.99,
            card_token='short'
        )
    
    assert 'Invalid card token' in str(exc_info.value)


def test_refund_success(payment_service, test_user, db_session):
    """Test successful refund processing."""
    # Create a completed payment
    payment = Payment(
        user_id=test_user.id,
        amount=99.99,
        card_token='tok_visa_4242424242424242',
        status=PaymentStatus.COMPLETED
    )
    db_session.add(payment)
    db_session.commit()
    
    # Process refund
    result = payment_service.refund(payment.id)
    
    assert result['payment_id'] == payment.id
    assert result['amount'] == 99.99
    assert result['status'] == 'refunded'
    assert 'refunded_at' in result


def test_refund_already_refunded(payment_service, test_user, db_session):
    """Test refunding an already refunded payment raises error."""
    # Create a refunded payment
    payment = Payment(
        user_id=test_user.id,
        amount=99.99,
        card_token='tok_visa_4242424242424242',
        status=PaymentStatus.REFUNDED
    )
    db_session.add(payment)
    db_session.commit()
    
    # Attempt to refund again
    with pytest.raises(RefundError) as exc_info:
        payment_service.refund(payment.id)
    
    assert 'already been refunded' in str(exc_info.value)


def test_refund_pending_payment(payment_service, test_user, db_session):
    """Test refunding a pending payment raises error."""
    # Create a pending payment
    payment = Payment(
        user_id=test_user.id,
        amount=99.99,
        card_token='tok_visa_4242424242424242',
        status=PaymentStatus.PENDING
    )
    db_session.add(payment)
    db_session.commit()
    
    # Attempt to refund
    with pytest.raises(RefundError) as exc_info:
        payment_service.refund(payment.id)
    
    assert 'Can only refund completed payments' in str(exc_info.value)


def test_list_payments_empty(payment_service, test_user):
    """Test listing payments for user with no payments."""
    payments = payment_service.list_user_payments(test_user.id)
    
    assert payments == []


def test_list_payments_with_data(payment_service, test_user, db_session):
    """Test listing payments for user with multiple payments."""
    # Create multiple payments
    for i in range(3):
        payment = Payment(
            user_id=test_user.id,
            amount=10.00 * (i + 1),
            card_token='tok_visa_4242424242424242',
            status=PaymentStatus.COMPLETED
        )
        db_session.add(payment)
    db_session.commit()
    
    payments = payment_service.list_user_payments(test_user.id)
    
    assert len(payments) == 3
    # Should be ordered by created_at desc (most recent first)
    assert payments[0]['amount'] == 30.00
    assert payments[1]['amount'] == 20.00
    assert payments[2]['amount'] == 10.00


def test_user_not_found(payment_service):
    """Test processing payment for non-existent user raises error."""
    with pytest.raises(UserNotFoundError) as exc_info:
        payment_service.process(
            user_id=99999,
            amount=99.99,
            card_token='tok_visa_4242424242424242'
        )
    
    assert 'User with ID 99999 not found' in str(exc_info.value)


def test_get_payment_not_found(payment_service):
    """Test retrieving non-existent payment returns None."""
    payment = payment_service.get_payment(99999)
    
    assert payment is None


def test_get_payment_success(payment_service, test_user, db_session):
    """Test retrieving existing payment."""
    # Create a payment
    payment = Payment(
        user_id=test_user.id,
        amount=99.99,
        card_token='tok_visa_4242424242424242',
        status=PaymentStatus.COMPLETED
    )
    db_session.add(payment)
    db_session.commit()
    
    # Retrieve payment
    result = payment_service.get_payment(payment.id)
    
    assert result is not None
    assert result['id'] == payment.id
    assert result['user_id'] == test_user.id
    assert result['amount'] == 99.99
    assert result['status'] == 'completed'


def test_list_payments_with_limit(payment_service, test_user, db_session):
    """Test listing payments respects limit parameter."""
    # Create 10 payments
    for i in range(10):
        payment = Payment(
            user_id=test_user.id,
            amount=10.00,
            card_token='tok_visa_4242424242424242',
            status=PaymentStatus.COMPLETED
        )
        db_session.add(payment)
    db_session.commit()
    
    # Request only 5
    payments = payment_service.list_user_payments(test_user.id, limit=5)
    
    assert len(payments) == 5

# Made with Bob
