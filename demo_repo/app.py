"""
Flask application for payment service API.
Provides REST endpoints for payment processing, refunds, and user authentication.
"""
import os
import logging
from datetime import timedelta
from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from werkzeug.security import check_password_hash, generate_password_hash

from models import Base, User, Payment, UserTier
from services.payment_service import (
    PaymentService,
    InvalidAmountError,
    InvalidCardError,
    PaymentNotFoundError,
    UserNotFoundError,
    RefundError,
    PaymentServiceError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

# Initialize JWT
jwt = JWTManager(app)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///payments.db')
engine = create_engine(DATABASE_URL, echo=False)
Base.metadata.create_all(engine)
SessionLocal = scoped_session(sessionmaker(bind=engine))


@app.teardown_appcontext
def remove_session(exception=None):
    """Remove database session after request."""
    SessionLocal.remove()


def get_db():
    """Get database session."""
    return SessionLocal()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'payment-api'}), 200


@app.route('/auth/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT token.
    
    Request body:
        {
            "email": "user@example.com",
            "password": "password123"
        }
    
    Returns:
        {
            "access_token": "jwt_token_here",
            "user": {...}
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password required'}), 400
        
        email = data['email']
        password = data['password']
        
        db = get_db()
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            logger.warning(f"Login attempt for non-existent user: {email}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # In production, verify password hash
        # For demo purposes, we'll accept any password
        
        access_token = create_access_token(identity=user.id)
        
        logger.info(f"User {user.id} logged in successfully")
        
        return jsonify({
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/payments/charge', methods=['POST'])
@jwt_required()
def charge_payment():
    """
    Process a payment charge.
    
    Request body:
        {
            "amount": 99.99,
            "card_token": "tok_visa_4242"
        }
    
    Returns:
        {
            "payment_id": 123,
            "user_id": 1,
            "amount": 99.99,
            "status": "completed",
            "created_at": "2024-01-01T12:00:00"
        }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'amount' not in data or 'card_token' not in data:
            return jsonify({'error': 'Amount and card_token required'}), 400
        
        amount = float(data['amount'])
        card_token = data['card_token']
        
        db = get_db()
        payment_service = PaymentService(db)
        
        result = payment_service.process(user_id, amount, card_token)
        
        logger.info(f"Payment processed: {result['payment_id']}")
        
        return jsonify(result), 201
        
    except InvalidAmountError as e:
        logger.warning(f"Invalid amount error: {e}")
        return jsonify({'error': str(e)}), 400
    except InvalidCardError as e:
        logger.warning(f"Invalid card error: {e}")
        return jsonify({'error': str(e)}), 400
    except UserNotFoundError as e:
        logger.error(f"User not found: {e}")
        return jsonify({'error': str(e)}), 404
    except PaymentServiceError as e:
        logger.error(f"Payment service error: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error in charge_payment: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/payments/<int:payment_id>', methods=['GET'])
@jwt_required()
def get_payment(payment_id):
    """
    Retrieve a payment by ID.
    
    Returns:
        {
            "id": 123,
            "user_id": 1,
            "amount": 99.99,
            "status": "completed",
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:00:00"
        }
    """
    try:
        user_id = get_jwt_identity()
        
        db = get_db()
        payment_service = PaymentService(db)
        
        payment = payment_service.get_payment(payment_id)
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Verify payment belongs to requesting user
        if payment['user_id'] != user_id:
            logger.warning(f"User {user_id} attempted to access payment {payment_id} belonging to user {payment['user_id']}")
            return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify(payment), 200
        
    except PaymentServiceError as e:
        logger.error(f"Error retrieving payment: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_payment: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/payments/refund', methods=['POST'])
@jwt_required()
def refund_payment():
    """
    Process a refund for a payment.
    
    Request body:
        {
            "payment_id": 123
        }
    
    Returns:
        {
            "payment_id": 123,
            "amount": 99.99,
            "status": "refunded",
            "refunded_at": "2024-01-01T12:30:00"
        }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'payment_id' not in data:
            return jsonify({'error': 'payment_id required'}), 400
        
        payment_id = int(data['payment_id'])
        
        db = get_db()
        payment_service = PaymentService(db)
        
        # Verify payment belongs to user
        payment = payment_service.get_payment(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        if payment['user_id'] != user_id:
            logger.warning(f"User {user_id} attempted to refund payment {payment_id} belonging to user {payment['user_id']}")
            return jsonify({'error': 'Unauthorized'}), 403
        
        result = payment_service.refund(payment_id)
        
        logger.info(f"Refund processed: {payment_id}")
        
        return jsonify(result), 200
        
    except PaymentNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except RefundError as e:
        logger.warning(f"Refund error: {e}")
        return jsonify({'error': str(e)}), 400
    except PaymentServiceError as e:
        logger.error(f"Payment service error: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error in refund_payment: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/users/<int:user_id>/payments', methods=['GET'])
@jwt_required()
def list_user_payments(user_id):
    """
    List all payments for a user.
    
    Query parameters:
        limit: Maximum number of payments to return (default: 50)
    
    Returns:
        {
            "payments": [...],
            "count": 10
        }
    """
    try:
        requesting_user_id = get_jwt_identity()
        
        # Users can only view their own payments
        if requesting_user_id != user_id:
            logger.warning(f"User {requesting_user_id} attempted to access payments for user {user_id}")
            return jsonify({'error': 'Unauthorized'}), 403
        
        limit = request.args.get('limit', 50, type=int)
        
        db = get_db()
        payment_service = PaymentService(db)
        
        payments = payment_service.list_user_payments(user_id, limit)
        
        return jsonify({
            'payments': payments,
            'count': len(payments)
        }), 200
        
    except UserNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except PaymentServiceError as e:
        logger.error(f"Error listing payments: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error in list_user_payments: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Create a test user for development
    db = get_db()
    test_user = db.query(User).filter(User.email == 'test@example.com').first()
    if not test_user:
        test_user = User(email='test@example.com', tier=UserTier.FREE)
        db.add(test_user)
        db.commit()
        logger.info(f"Created test user: {test_user.id}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

# Made with Bob
