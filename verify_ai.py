import requests
import json
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

# --- CONFIGURATION ---
BASE_URL = "http://localhost:8000/v1/api"
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")

def print_res(step, response):
    if response.status_code in [200, 201]:
        print(f"✅ {step}: Success")
    else:
        print(f"❌ {step}: Failed ({response.status_code})")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        exit()

def get_signature(payload_body):
    """Calculates the HMAC-SHA256 signature to mimic WhatsApp."""
    if not APP_SECRET:
        print("❌ Error: WHATSAPP_APP_SECRET not found. Please check your .env file.")
        exit(1)
        
    json_bytes = json.dumps(payload_body, separators=(',', ':')).encode()
    mac = hmac.new(APP_SECRET.encode(), msg=json_bytes, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}", json_bytes

def test_flow():
    print("--- 🚀 Starting Full System Verification ---")

    # 1. Simulate Incoming Webhook
    print("\n🔹 Step 1: Simulating Incoming WhatsApp Message...")
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": "123456789"},
                    "messages": [{
                        "from": "919999999999",
                        "id": "wamid.Test12345",
                        "type": "text",
                        "text": {"body": "I am interested in the enterprise plan prices."}
                    }]
                }
            }]
        }]
    }
    
    signature, body_bytes = get_signature(webhook_payload)
    headers = {
        "X-Hub-Signature": signature,
        "Content-Type": "application/json"
    }
    
    r = requests.post(f"{BASE_URL}/webhooks/whatsapp", data=body_bytes, headers=headers)
    print_res("Webhook Trigger", r)

    # Allow async workers to process
    print("⏳ Waiting 2 seconds for Celery workers...")
    time.sleep(2)

    # 2. Verify Conversation Created
    print("\n🔹 Step 2: Verifying Conversation Persistence...")
    # Note: Using the Chat router endpoint
    r = requests.get(f"{BASE_URL}/chat/conversations")
    print_res("List Conversations", r)
    
    data = r.json()
    if not data:
        print("❌ No conversations found! (Worker might have failed)")
        exit()
    
    # Find our mocked conversation
    target_convo = next((c for c in data if c.get('customer_number') == "919999999999"), data[0])
    convo_id = target_convo['id']
    print(f"   > Conversation ID: {convo_id}")

    # 3. Verify Message & AI Processing
    r = requests.get(f"{BASE_URL}/chat/conversations/{convo_id}")
    print_res("Get Messages", r)
    msgs = r.json()
    msg_id = msgs[0]['id']
    
    print(f"   > Message ID: {msg_id}")
    print(f"   > Intent: {msgs[0].get('intent')}")
    # If the worker ran, this should not be 'unknown'
    print(f"   > Sentiment: {msgs[0].get('sentiment')}") 

    # 4. Test Vector Search
    print("\n🔹 Step 3: Testing Vector Search (OpenAI)...")
    # This endpoint now expects 'text' as a query param
    r = requests.get(f"{BASE_URL}/vector/similar", params={"text": "enterprise plan cost"})
    print_res("Vector Search", r)
    print(f"   > Found {len(r.json())} similar messages.")

    # 5. Test AI Reply Suggestion
    print("\n🔹 Step 4: Testing AI Reply Generation (RAG)...")
    r = requests.post(f"{BASE_URL}/ai/replies/{convo_id}")
    print_res("Generate Replies", r)
    
    suggestions = r.json()
    if suggestions:
        print("   > AI Suggestions:")
        for s in suggestions:
            print(f"     - [{s['rank']}] {s['suggestion']}")
    else:
        print("   > No suggestions returned.")

if __name__ == "__main__":
    test_flow()