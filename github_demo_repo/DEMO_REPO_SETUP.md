# Demo GitHub Repository Setup Guide

This document explains what should be in your demo GitHub repository that PHRAXIS will modify during demonstrations.

## Repository Purpose

The demo repository serves as the **target codebase** that PHRAXIS will analyze and modify. During the hackathon demo, when you speak a feature request (e.g., "Add rate limiting"), PHRAXIS will:

1. **Architect Mode**: Read and analyze this entire repository
2. **Plan Mode**: Create an implementation plan for the requested feature
3. **Code Mode**: Generate actual code files with the implementation
4. **GitHub Integration**: Open a pull request with the generated changes

## Recommended Repository Structure

```
demo_repo/                          # Your GitHub repository
├── README.md                       # Project description
├── requirements.txt                # Python dependencies
├── .gitignore                      # Git ignore file
├── app.py                          # Main FastAPI application
├── models.py                       # Database models
├── config.py                       # Configuration
├── middleware/                     # Middleware components
│   └── __init__.py
├── services/                       # Business logic services
│   ├── __init__.py
│   ├── payment_service.py         # Example: Payment processing
│   ├── user_service.py            # Example: User management
│   └── auth_service.py            # Example: Authentication
├── routes/                         # API route handlers
│   ├── __init__.py
│   ├── payment_routes.py
│   └── user_routes.py
└── tests/                          # Test files
    ├── __init__.py
    ├── test_payment.py
    └── test_user.py
```

## What to Include

### 1. **Core Application Files**

**app.py** - Main FastAPI application:
```python
from fastapi import FastAPI
from routes import payment_routes, user_routes

app = FastAPI(title="Demo Payment Service")

# Include routers
app.include_router(payment_routes.router, prefix="/api/payments")
app.include_router(user_routes.router, prefix="/api/users")

@app.get("/")
def root():
    return {"message": "Demo Payment Service API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

**models.py** - Database models:
```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class User(BaseModel):
    id: int
    email: str
    username: str
    tier: str = "free"  # free or premium
    created_at: datetime

class Payment(BaseModel):
    id: int
    user_id: int
    amount: float
    currency: str = "USD"
    status: str  # pending, completed, failed
    created_at: datetime
```

**services/payment_service.py** - Business logic:
```python
from models import Payment, User
from typing import List

class PaymentService:
    def __init__(self):
        self.payments = []
    
    def process_payment(self, user_id: int, amount: float) -> Payment:
        """Process a payment for a user."""
        payment = Payment(
            id=len(self.payments) + 1,
            user_id=user_id,
            amount=amount,
            currency="USD",
            status="pending",
            created_at=datetime.utcnow()
        )
        self.payments.append(payment)
        return payment
    
    def get_user_payments(self, user_id: int) -> List[Payment]:
        """Get all payments for a user."""
        return [p for p in self.payments if p.user_id == user_id]
```

**routes/payment_routes.py** - API routes:
```python
from fastapi import APIRouter, HTTPException
from services.payment_service import PaymentService
from models import Payment

router = APIRouter()
payment_service = PaymentService()

@router.post("/", response_model=Payment)
def create_payment(user_id: int, amount: float):
    """Create a new payment."""
    return payment_service.process_payment(user_id, amount)

@router.get("/{user_id}", response_model=List[Payment])
def get_payments(user_id: int):
    """Get all payments for a user."""
    return payment_service.get_user_payments(user_id)
```

### 2. **Configuration Files**

**requirements.txt**:
```
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
pytest==7.4.3
```

**.gitignore**:
```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
.env
.venv
*.db
*.sqlite
*.log
.pytest_cache/
.coverage
htmlcov/
```

### 3. **Tests**

**tests/test_payment.py**:
```python
import pytest
from services.payment_service import PaymentService

def test_process_payment():
    service = PaymentService()
    payment = service.process_payment(user_id=1, amount=100.0)
    assert payment.amount == 100.0
    assert payment.status == "pending"

def test_get_user_payments():
    service = PaymentService()
    service.process_payment(user_id=1, amount=100.0)
    service.process_payment(user_id=1, amount=50.0)
    payments = service.get_user_payments(user_id=1)
    assert len(payments) == 2
```

### 4. **Documentation**

**README.md**:
```markdown
# Demo Payment Service

A simple payment processing service built with FastAPI.

## Features

- Payment processing
- User management
- RESTful API

## Setup

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## API Endpoints

- `POST /api/payments/` - Create payment
- `GET /api/payments/{user_id}` - Get user payments
- `GET /health` - Health check
```

## Demo Scenario Examples

### Example 1: Rate Limiting Feature

**Voice Command**: "Add rate limiting — 100 requests per minute for free users and 1000 for premium. Return 429 with a retry-after header."

**Expected PHRAXIS Actions**:
1. Architect: Identifies `middleware/` directory and `app.py`
2. Plan: Creates steps to add rate limiting middleware
3. Code: Generates:
   - `middleware/rate_limiter.py` - Rate limiting logic
   - Updates to `app.py` - Adds middleware
   - Updates to `models.py` - Adds rate limit tracking
   - `tests/test_rate_limiter.py` - Tests for rate limiting

### Example 2: Authentication Feature

**Voice Command**: "Add JWT authentication with login and token refresh endpoints."

**Expected PHRAXIS Actions**:
1. Architect: Identifies `services/`, `routes/`, and `middleware/`
2. Plan: Creates authentication implementation plan
3. Code: Generates:
   - `services/auth_service.py` - JWT token generation
   - `routes/auth_routes.py` - Login/refresh endpoints
   - `middleware/auth_middleware.py` - Token validation
   - Updates to `models.py` - User authentication fields

### Example 3: Caching Layer

**Voice Command**: "Add Redis caching for payment queries with 5-minute TTL."

**Expected PHRAXIS Actions**:
1. Architect: Identifies `services/payment_service.py` and `config.py`
2. Plan: Creates caching implementation plan
3. Code: Generates:
   - `services/cache_service.py` - Redis integration
   - Updates to `services/payment_service.py` - Cache integration
   - Updates to `requirements.txt` - Adds redis dependency
   - `tests/test_cache.py` - Cache tests

## Repository Setup Instructions

### Step 1: Create GitHub Repository

```bash
# Create new repository on GitHub
# Name: demo-payment-service (or your choice)
# Visibility: Public or Private
```

### Step 2: Initialize Local Repository

```bash
# Clone or create locally
git init demo-payment-service
cd demo-payment-service

# Create the structure
mkdir -p services routes middleware tests
touch app.py models.py config.py requirements.txt README.md .gitignore
touch services/__init__.py services/payment_service.py
touch routes/__init__.py routes/payment_routes.py
touch middleware/__init__.py
touch tests/__init__.py tests/test_payment.py
```

### Step 3: Add Initial Code

Copy the example code from this document into the respective files.

### Step 4: Commit and Push

```bash
git add .
git commit -m "Initial commit: Demo payment service"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/demo-payment-service.git
git push -u origin main
```

### Step 5: Configure PHRAXIS

Update your `.env` file:
```bash
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO_OWNER=your_github_username
GITHUB_REPO_NAME=demo-payment-service
```

## GitHub Token Setup

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name: "PHRAXIS Demo Token"
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
5. Click "Generate token"
6. Copy the token immediately (you won't see it again!)
7. Add to your `.env` file as `GITHUB_TOKEN`

## Best Practices for Demo Repository

### 1. **Keep It Simple**
- Use clear, descriptive names
- Follow standard Python/FastAPI patterns
- Include comments explaining key concepts

### 2. **Make It Realistic**
- Use real-world scenarios (payments, users, etc.)
- Include proper error handling
- Add basic validation

### 3. **Ensure Modifiability**
- Keep functions small and focused
- Use clear separation of concerns
- Make it easy for Bob to identify where to add features

### 4. **Include Tests**
- Add basic test coverage
- Use pytest for testing
- Make tests easy to extend

### 5. **Document Well**
- Clear README with setup instructions
- Inline comments for complex logic
- API documentation

## Testing Your Demo Repository

Before the hackathon demo, test that PHRAXIS can:

1. **Read the repository**: Bob Architect mode should successfully analyze all files
2. **Understand the structure**: Bob should identify correct files to modify
3. **Generate valid code**: Generated code should follow your patterns
4. **Create PRs**: GitHub integration should work smoothly

### Test Command

```bash
# From PHRAXIS directory
cd backend
python -c "
from services.bob_orchestrator import BobOrchestrator
orchestrator = BobOrchestrator()
intent = {
    'action': 'add_rate_limiting',
    'target_module': 'middleware',
    'parameters': {'per_minute_limit': 100},
    'constraints': []
}
result = orchestrator.orchestrate(intent, '../demo_repo')
print(f'Success! Generated {len(result[\"files_generated\"])} files')
"
```

## Troubleshooting

### Issue: Bob can't read repository
- **Solution**: Ensure all files have proper Python syntax
- **Solution**: Check file permissions

### Issue: Generated code doesn't match style
- **Solution**: Add more example code in similar style
- **Solution**: Include style guide comments

### Issue: PR creation fails
- **Solution**: Verify GitHub token has correct permissions
- **Solution**: Check repository name in `.env`

### Issue: Bob generates incorrect files
- **Solution**: Improve repository structure clarity
- **Solution**: Add more descriptive function/class names

## Demo Day Checklist

- [ ] Repository is public or token has access
- [ ] All files have proper syntax
- [ ] Tests pass locally
- [ ] GitHub token is valid and has correct permissions
- [ ] `.env` file has correct repository details
- [ ] PHRAXIS backend and frontend are running
- [ ] Test voice command works end-to-end
- [ ] PR creation works
- [ ] Demo scenario is rehearsed

## Example Demo Script

1. **Start PHRAXIS**: Open frontend at http://localhost:5173
2. **Show Repository**: Display demo repository on GitHub
3. **Speak Command**: "Add rate limiting — 100 requests per minute for free users and 1000 for premium"
4. **Watch Magic**: Show real-time progress in PHRAXIS UI
5. **Show PR**: Open created PR on GitHub
6. **Highlight Speed**: Point out it took under 4 minutes
7. **Show Code Quality**: Review generated code in PR

## Additional Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **GitHub API**: https://docs.github.com/en/rest
- **IBM Bob Documentation**: Check BOB_USAGE.md in PHRAXIS root

---

**Made with Bob** 🤖

For questions or issues, refer to the main PHRAXIS documentation or AGENTS.md file.