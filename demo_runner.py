"""
PHRAXIS Demo Runner
Tests all IBM service connections and verifies the application is ready to run.
"""
import sys
import os
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path.parent))

from backend.env_loader import get_config, EnvironmentError
from backend.services.stt_service import STTService, STTServiceError
from backend.services.nlu_service import NLUService, NLUServiceError
from backend.services.cloudant_service import CloudantService, CloudantServiceError
from backend.services.watsonx_service import WatsonxService, WatsonxServiceError
from backend.services.github_service import GitHubService, GitHubServiceError


def print_header():
    """Print demo runner header."""
    print("=" * 60)
    print("PHRAXIS - Voice-to-Code System")
    print("IBM Watson + IBM Bob Integration")
    print("=" * 60)
    print()


def test_service(service_name: str, test_func) -> bool:
    """
    Test a service connection.
    
    Args:
        service_name: Name of the service to test
        test_func: Function that tests the service
    
    Returns:
        True if test passed, False otherwise
    """
    try:
        print(f"Testing {service_name}...", end=" ", flush=True)
        test_func()
        print(f"✓ {service_name}: connected")
        return True
    except Exception as e:
        print(f"✗ {service_name}: FAILED")
        print(f"  Error: {str(e)}")
        return False


def main():
    """Main demo runner function."""
    print_header()
    
    # Step 1: Load and validate environment variables
    print("Step 1: Loading environment variables...")
    try:
        config = get_config()
        print("✓ Environment variables loaded successfully")
        print()
    except EnvironmentError as e:
        print("✗ Environment validation failed:")
        print(str(e))
        print()
        print("Please create a .env file with all required credentials.")
        print("See .env.example for the required variables.")
        sys.exit(1)
    
    # Step 2: Test IBM Watson Speech-to-Text
    print("Step 2: Testing IBM service connections...")
    print()
    
    services_ok = True
    
    # Test STT
    def test_stt():
        stt = STTService()
        if not stt.health_check():
            raise STTServiceError("Health check failed")
    
    if not test_service("IBM Watson STT", test_stt):
        services_ok = False
    
    # Test NLU
    def test_nlu():
        nlu = NLUService()
        if not nlu.health_check():
            raise NLUServiceError("Health check failed")
    
    if not test_service("IBM Watson NLU", test_nlu):
        services_ok = False
    
    # Test Cloudant
    def test_cloudant():
        cloudant = CloudantService()
        if not cloudant.health_check():
            raise CloudantServiceError("Health check failed")
    
    if not test_service("IBM Cloudant", test_cloudant):
        services_ok = False
    
    # Test WatsonX
    def test_watsonx():
        watsonx = WatsonxService()
        if not watsonx.health_check():
            raise WatsonxServiceError("Health check failed")
    
    if not test_service("watsonx.ai", test_watsonx):
        services_ok = False
    
    # Test GitHub
    def test_github():
        github = GitHubService()
        if not github.health_check():
            raise GitHubServiceError("Health check failed")
    
    if not test_service("GitHub API", test_github):
        services_ok = False
    
    print()
    
    # Step 3: Final status
    if not services_ok:
        print("=" * 60)
        print("✗ Some services failed to connect")
        print("Please check your credentials and network connection")
        print("=" * 60)
        sys.exit(1)
    
    print("=" * 60)
    print("✓ All services connected successfully!")
    print()
    print("PHRAXIS is ready to run.")
    print()
    print("To start the backend server:")
    print("  cd backend")
    print("  uvicorn main:app --reload --port 8000")
    print()
    print("To start the frontend:")
    print("  cd frontend")
    print("  npm run dev")
    print()
    print("Then open http://localhost:5173 in your browser")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo runner interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
