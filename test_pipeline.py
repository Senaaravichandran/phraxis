"""
Test script to verify the PHRAXIS end-to-end pipeline.
"""
import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n1. Testing health endpoint...")
    response = requests.get(f"{API_BASE}/api/health")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Overall status: {data['status']}")
        print(f"   Services: {data['services']}")
        return True
    return False

def test_intent_extraction():
    """Test intent extraction"""
    print("\n2. Testing intent extraction...")
    test_transcript = "Add rate limiting to the payment service with 100 requests per minute for free users"
    
    response = requests.post(
        f"{API_BASE}/api/intent/extract",
        json={"transcript": test_transcript}
    )
    
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Intent ID: {data['intent_doc_id']}")
        print(f"   Action: {data['action']}")
        print(f"   Target: {data['target_module']}")
        print(f"   Confidence: {data['confidence']}")
        return data['intent_doc_id']
    else:
        print(f"   Error: {response.text}")
    return None

def test_code_generation(intent_doc_id):
    """Test code generation SSE endpoint"""
    print("\n3. Testing code generation (SSE)...")
    print(f"   Intent ID: {intent_doc_id}")
    
    url = f"{API_BASE}/api/generate/code?intent_doc_id={intent_doc_id}&repo_path=demo_repo"
    print(f"   URL: {url}")
    
    try:
        response = requests.get(url, stream=True, timeout=300)
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("   Streaming events:")
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    print(f"     {decoded}")
                    if decoded.startswith('data:'):
                        try:
                            event_data = json.loads(decoded[5:].strip())
                            if event_data.get('type') == 'complete':
                                print("   [OK] Code generation complete!")
                                return True
                            elif event_data.get('type') == 'error':
                                print(f"   [ERROR] Error: {event_data.get('message')}")
                                return False
                        except json.JSONDecodeError:
                            pass
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"   Exception: {e}")
        return False
    
    return False

def test_list_intents():
    """Test listing intents"""
    print("\n4. Testing list intents...")
    response = requests.get(f"{API_BASE}/api/intents?limit=5")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Found {data['count']} intents")
        return True
    return False

def main():
    print("="*60)
    print("PHRAXIS End-to-End Pipeline Test")
    print("="*60)
    
    # Test 1: Health check
    if not test_health():
        print("\n[FAIL] Health check failed. Exiting.")
        return
    
    # Test 2: Intent extraction
    intent_id = test_intent_extraction()
    if not intent_id:
        print("\n[FAIL] Intent extraction failed. Exiting.")
        return
    
    # Test 3: Code generation (SSE)
    print("\n[WARNING] Code generation test will take several minutes...")
    print("   This calls Bob to actually generate code.")
    user_input = input("   Continue? (y/n): ")
    if user_input.lower() == 'y':
        test_code_generation(intent_id)
    else:
        print("   Skipped code generation test.")
    
    # Test 4: List intents
    test_list_intents()
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)

if __name__ == "__main__":
    main()

# Made with Bob
