import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from env_loader import get_config
from services.github_service import GitHubService

config = get_config()
svc = GitHubService()

test_intent = {
    "action": "add_feature",
    "parameters": {},
    "constraints": [],
    "raw_text": "Add a hello greeting",
    "confidence": 0.85,
}

test_files = {
    "src/greeting.py": 'def greet(name):\n    return f"Hello, {name}!"\n'
}

print("Testing PR creation...")
try:
    result = svc.create_pr(
        repo_owner=config.GITHUB_REPO_OWNER,
        repo_name=config.GITHUB_REPO_NAME,
        branch_name="phraxis/test-20260516-2",
        files_changed=test_files,
        intent=test_intent,
        transcript="Add a hello greeting",
    )
    print(f"SUCCESS: {result['pr_url']}")
except Exception as e:
    print(f"FAILED: {e}")
