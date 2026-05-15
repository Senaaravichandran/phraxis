# IBM Bob Usage in PHRAXIS

## Overview

PHRAXIS uses IBM Bob as its core intelligence engine, leveraging Bob's unique ability to read entire codebases and generate context-aware code. This document details exactly how Bob is integrated and used throughout the platform.

## Bob's Role in PHRAXIS

IBM Bob is not just a code generator—it's the **repository intelligence layer** that makes PHRAXIS possible. Bob provides:

1. **Full Repository Context**: Reads every file before generating code
2. **Pattern Recognition**: Identifies and matches existing code patterns
3. **Multi-Phase Workflow**: Architect → Plan → Code orchestration
4. **Production-Ready Output**: Generates code that fits seamlessly
5. **Automated Validation**: Reviews code before PR submission

## Bob Modes Used in PHRAXIS

### 1. Architect Mode

**Purpose**: Analyze repository structure and identify change locations

**How It's Used**:
```python
from backend.services.bob_shell_runner import BobShellRunner

runner = BobShellRunner()
result = runner.run_architect(
    repo_path="../demo_repo",
    task_description="Add rate limiting with tier-based limits"
)
```

**Bob Command Executed**:
```bash
bob --non-interactive "Switch to Architect mode. Read every file in ../demo_repo. Map all functions, classes, imports, and patterns. Identify which files and functions need to change to implement: add_rate_limiting with parameters {free_tier_limit: 100, premium_limit: 1000, error_code: 429}. Output as JSON: {files_to_modify: [], new_files_to_create: [], functions_to_change: [], patterns_used: []}"
```

**What Bob Does**:
- Reads `app.py`, `models.py`, `services/payment_service.py`, `tests/test_payment.py`
- Maps all Flask routes and their decorators
- Identifies the `@jwt_required` authentication pattern
- Discovers the User model with tier field
- Locates existing error handling patterns
- Determines that middleware should be created
- Identifies all endpoints that need rate limiting

**Output Example**:
```json
{
  "files_to_modify": [
    "app.py"
  ],
  "new_files_to_create": [
    "middleware/rate_limiter.py",
    "tests/test_rate_limiter.py"
  ],
  "functions_to_change": [
    "app.py:charge_payment",
    "app.py:get_payment",
    "app.py:refund_payment",
    "app.py:list_user_payments"
  ],
  "patterns_used": [
    "Flask route decorators (@app.route)",
    "JWT authentication (@jwt_required)",
    "User tier from get_jwt_identity()",
    "HTTPException for errors",
    "Logging with logger.info/error"
  ]
}
```

**Why This Is Critical**: Bob doesn't guess where changes should go—it READS the code and KNOWS. This ensures generated code integrates perfectly.

### 2. Plan Mode

**Purpose**: Create step-by-step implementation plan

**How It's Used**:
```python
plan = runner.run_plan(
    context=architect_result,
    task_description="Add rate limiting with tier-based limits"
)
```

**Bob Command Executed**:
```bash
bob --non-interactive "Switch to Plan mode. Given this repository map: {architect_output}. Create a step-by-step implementation plan for: add rate limiting with tier-based limits. Each step must specify: file path, function name, exact change description, and whether it is a modify or create operation. Output as JSON array of steps."
```

**What Bob Does**:
- Analyzes the architect output
- Orders changes logically (dependencies first)
- Breaks down into atomic steps
- Specifies exact file paths and operations
- Ensures nothing is missed

**Output Example**:
```json
[
  {
    "step": 1,
    "file_path": "middleware/rate_limiter.py",
    "operation": "create",
    "description": "Create RateLimiter middleware with tier-based limits",
    "details": "Implement decorator that checks user tier and enforces limits"
  },
  {
    "step": 2,
    "file_path": "middleware/__init__.py",
    "operation": "create",
    "description": "Create middleware package init file",
    "details": "Export rate_limit decorator"
  },
  {
    "step": 3,
    "file_path": "app.py",
    "function_name": "charge_payment",
    "operation": "modify",
    "description": "Add @rate_limit decorator to charge_payment",
    "details": "Insert decorator before @jwt_required"
  },
  {
    "step": 4,
    "file_path": "app.py",
    "function_name": "get_payment",
    "operation": "modify",
    "description": "Add @rate_limit decorator to get_payment",
    "details": "Insert decorator before @jwt_required"
  },
  {
    "step": 5,
    "file_path": "tests/test_rate_limiter.py",
    "operation": "create",
    "description": "Create comprehensive tests for rate limiter",
    "details": "Test free tier limits, premium limits, 429 responses, retry-after headers"
  }
]
```

**Why This Is Critical**: The plan ensures changes are made in the right order and nothing is forgotten. Each step is testable and atomic.

### 3. Code Mode

**Purpose**: Generate actual code for each planned step

**How It's Used**:
```python
for step in plan:
    code = runner.run_code(
        file_path=step['file_path'],
        instruction=step['description'],
        context={'architect': architect_result, 'plan': plan}
    )
    # Save generated code to file
```

**Bob Command Executed** (for each step):
```bash
bob --non-interactive "Switch to Code mode. With context: {architect and plan data}. Implement this specific change in middleware/rate_limiter.py: Create RateLimiter middleware with tier-based limits. Follow the existing code patterns exactly. Write the complete file content."
```

**What Bob Does**:
- Generates complete file content (not snippets)
- Matches existing code style exactly
- Uses discovered patterns (decorators, error handling, logging)
- Includes proper docstrings and comments
- Follows naming conventions
- Adds type hints where used in existing code

**Output Example** (middleware/rate_limiter.py):
```python
"""
Rate limiting middleware for payment API.
Implements tier-based rate limiting with retry-after headers.
"""
import time
import logging
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from models import User

logger = logging.getLogger(__name__)

# In-memory rate limit storage (use Redis in production)
rate_limit_storage = {}

RATE_LIMITS = {
    'free': 100,      # 100 requests per minute
    'premium': 1000   # 1000 requests per minute
}

WINDOW_SIZE = 60  # 1 minute in seconds


def rate_limit(f):
    """
    Rate limiting decorator that enforces tier-based request limits.
    
    Free tier: 100 requests per minute
    Premium tier: 1000 requests per minute
    
    Returns 429 with retry-after header when limit exceeded.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user_id = get_jwt_identity()
            
            # Get user tier from database
            from app import get_db
            db = get_db()
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.error(f"User not found for rate limiting: {user_id}")
                return jsonify({'error': 'User not found'}), 404
            
            tier = user.tier.value
            limit = RATE_LIMITS.get(tier, RATE_LIMITS['free'])
            
            # Initialize storage for this user
            if user_id not in rate_limit_storage:
                rate_limit_storage[user_id] = []
            
            # Clean old requests outside the window
            current_time = time.time()
            rate_limit_storage[user_id] = [
                req_time for req_time in rate_limit_storage[user_id]
                if current_time - req_time < WINDOW_SIZE
            ]
            
            # Check if limit exceeded
            if len(rate_limit_storage[user_id]) >= limit:
                oldest_request = min(rate_limit_storage[user_id])
                retry_after = int(WINDOW_SIZE - (current_time - oldest_request)) + 1
                
                logger.warning(
                    f"Rate limit exceeded for user {user_id} (tier: {tier}). "
                    f"Limit: {limit}, Current: {len(rate_limit_storage[user_id])}"
                )
                
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'limit': limit,
                    'window': 'minute',
                    'retry_after': retry_after
                }), 429, {'Retry-After': str(retry_after)}
            
            # Add current request
            rate_limit_storage[user_id].append(current_time)
            
            logger.info(
                f"Rate limit check passed for user {user_id} (tier: {tier}). "
                f"Requests: {len(rate_limit_storage[user_id])}/{limit}"
            )
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error in rate limiting: {e}")
            # Fail open - don't block requests on rate limiter errors
            return f(*args, **kwargs)
    
    return decorated_function
```

**Why This Is Critical**: Bob generates COMPLETE, PRODUCTION-READY code that matches the existing codebase style. Notice:
- Uses the same logging format as existing code
- Follows the same error handling pattern
- Matches the docstring style
- Uses the same import organization
- Includes the same level of comments

### 4. Orchestrate Mode

**Purpose**: Autonomously coordinate Architect → Plan → Code sequence

**How It's Used**:
```python
from backend.services.bob_orchestrator import BobOrchestrator

orchestrator = BobOrchestrator()
result = orchestrator.orchestrate(
    intent={
        "action": "add_rate_limiting",
        "parameters": {"free_tier_limit": 100, "premium_limit": 1000}
    },
    repo_path="../demo_repo"
)
```

**What Bob Does**:
- Automatically switches between modes
- Passes context from Architect to Plan to Code
- Handles errors and retries
- Exports complete session data
- Returns structured results

**Output Example**:
```json
{
  "plan": [...],
  "files_generated": {
    "middleware/rate_limiter.py": "...",
    "middleware/__init__.py": "...",
    "tests/test_rate_limiter.py": "..."
  },
  "code_changes": {
    "app.py": {
      "charge_payment": "Added @rate_limit decorator",
      "get_payment": "Added @rate_limit decorator",
      ...
    }
  },
  "bob_session_id": "bob_session_20240115_143022_abc123",
  "execution_time": 165.3
}
```

**Why This Is Critical**: Orchestrate mode handles the entire workflow automatically, ensuring consistency and proper context flow between phases.

### 5. Ask Mode

**Purpose**: Explain generated code for PR descriptions

**How It's Used**:
```python
explanation = runner.run_ask(
    question="Explain the rate limiting implementation",
    context={"generated_code": files_generated}
)
```

**Bob Command Executed**:
```bash
bob --non-interactive "Switch to Ask mode. Explain this rate limiting implementation: {code}. Focus on: what it does, how it works, and why these design decisions were made."
```

**What Bob Does**:
- Analyzes the generated code
- Explains the implementation approach
- Highlights key design decisions
- Provides context for reviewers

**Output Example**:
```markdown
## Rate Limiting Implementation

This implementation adds tier-based rate limiting to the payment API:

### What It Does
- Limits free tier users to 100 requests per minute
- Limits premium tier users to 1000 requests per minute
- Returns 429 status with retry-after header when limit exceeded
- Integrates seamlessly with existing JWT authentication

### How It Works
1. The `@rate_limit` decorator wraps protected endpoints
2. Extracts user ID from JWT token
3. Looks up user tier from database
4. Tracks requests in a sliding window (60 seconds)
5. Enforces tier-specific limits
6. Returns 429 with retry-after header when exceeded

### Design Decisions
- **In-memory storage**: Simple for demo, should use Redis in production
- **Sliding window**: More accurate than fixed windows
- **Fail open**: Rate limiter errors don't block requests
- **Decorator pattern**: Matches existing @jwt_required pattern
- **Retry-after header**: Follows HTTP standards (RFC 6585)
```

**Why This Is Critical**: Bob's explanations provide context for code reviewers, making PRs self-documenting.

### 6. Bob Shell

**Purpose**: Non-interactive command execution from Python

**How It's Implemented**:
```python
import subprocess
import json

def execute_bob_command(command: str, timeout: int = 120):
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    # Parse JSON output
    output = json.loads(result.stdout)
    
    # Save session
    session_file = f"bob_sessions/session_{timestamp}.json"
    with open(session_file, 'w') as f:
        json.dump({
            "command": command,
            "output": output,
            "timestamp": timestamp
        }, f)
    
    return output
```

**Why This Is Critical**: Bob Shell enables programmatic Bob access, allowing PHRAXIS to automate the entire workflow without manual intervention.

### 7. /init Command (AGENTS.md Generation)

**Purpose**: Generate AGENTS.md for cross-session context persistence

**How It's Used**:
```bash
bob /init
```

**What Bob Does**:
- Analyzes the codebase structure
- Identifies build/test commands
- Extracts code style guidelines
- Documents non-obvious patterns
- Creates AGENTS.md file

**Output**: The AGENTS.md file at the root of this repository

**Why This Is Critical**: AGENTS.md provides context for future Bob sessions, ensuring consistency across multiple interactions.

### 8. /review Command

**Purpose**: Validate generated code before PR submission

**How It's Used**:
```python
review_result = runner.run_review(repo_path="../demo_repo")
```

**Bob Command Executed**:
```bash
bob --non-interactive "review ../demo_repo"
```

**What Bob Does**:
- Checks for bugs and logic errors
- Validates security (no hardcoded secrets)
- Ensures code style consistency
- Verifies test coverage
- Identifies performance issues

**Output Example**:
```json
{
  "issues": [],
  "warnings": [
    "In-memory rate limiting should use Redis in production"
  ],
  "suggestions": [
    "Consider adding rate limit metrics/monitoring",
    "Add configuration for rate limit values"
  ],
  "overall_status": "pass"
}
```

**Why This Is Critical**: Bob's review ensures generated code meets quality standards before the PR is opened.

### 9. Custom Mode: "phraxis-builder"

**Purpose**: Pre-loaded context for demo_repo to conserve Bobcoins

**How It's Created**:
```bash
bob --create-mode phraxis-builder --context ../demo_repo
```

**What It Does**:
- Pre-loads demo_repo structure into Bob's context
- Caches file contents and patterns
- Reduces token usage for repeated operations
- Speeds up subsequent generations

**How It's Used**:
```bash
bob --mode phraxis-builder "Add rate limiting"
```

**Why This Is Critical**: Custom modes reduce latency and cost for repeated operations on the same codebase.

## Bob Session Export

**Requirement**: All Bob task session files must be exported for judging

**Implementation**:
```python
class BobShellRunner:
    def _save_session(self, command, stdout, stderr, exit_code):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"bob_session_{timestamp}.json"
        filepath = Path("bob_sessions") / filename
        
        session_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr
        }
        
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        return str(filepath)
```

**Session Files Include**:
- Complete Bob command executed
- Full stdout and stderr output
- Timestamp and execution time
- Exit code and error information
- Parsed JSON results

**Location**: All sessions saved to `bob_sessions/` directory

## Why Bob Is Irreplaceable

### 1. Full Repository Context
- **Generic AI**: Generates code based on prompt alone
- **IBM Bob**: Reads ENTIRE codebase first, understands all patterns

### 2. Pattern Matching
- **Generic AI**: Uses common patterns
- **IBM Bob**: Uses YOUR patterns from YOUR codebase

### 3. Multi-Phase Intelligence
- **Generic AI**: Single-shot generation
- **IBM Bob**: Architect → Plan → Code workflow

### 4. Production-Ready Output
- **Generic AI**: Requires extensive manual adaptation
- **IBM Bob**: Generates code that fits seamlessly

### 5. Automated Validation
- **Generic AI**: No quality checks
- **IBM Bob**: Built-in review mode validates before PR

## Conclusion

IBM Bob is not just a tool in PHRAXIS—it IS PHRAXIS. Without Bob's ability to:
- Read entire repositories
- Understand existing patterns
- Generate context-aware code
- Orchestrate multi-phase workflows
- Validate output quality

...PHRAXIS would be impossible. Bob transforms voice-to-code from a dream into reality.

---

**IBM Bob: The intelligence engine that makes voice-to-impact possible.**