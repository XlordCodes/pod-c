import requests
import json
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv

# 1. Load environment variables from the .env file
load_dotenv()

# --- CONFIGURATION ---
BASE_URL = "http://localhost:8000/api"
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")

def print_res(step, response):
    if response.status_code == 200:
        print(f"✅ {step}: Success")
    else:
        print(f"❌ {step}: Failed ({response.status_code})")
        print(response.text)
        exit()

def get_signature(payload_body):
    """Calculates the HMAC-SHA256 signature to mimic WhatsApp."""
    if not APP_SECRET:
        print("❌ Error: WHATSAPP_APP_SECRET not found. Please check your .env file.")
        exit(1)
        
    # We use separators to mimic the tight JSON packing usually sent by APIs
    json_bytes = json.dumps(payload_body, separators=(',', ':')).encode()
    
    mac = hmac.new(APP_SECRET.encode(), msg=json_bytes, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}", json_bytes

def test_flow():
    print("--- 🚀 Starting AI Module Verification ---")

    # 1. Simulate Incoming Webhook (Module 3)
    print("\n🔹 Step 1: Simulating Incoming Message (Module 3)...")
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {
                        "phone_number_id": "123456789" # Matches typical meta structure
                    },
                    "messages": [{
                        "from": "919999999999",
                        "id": "wamid.HBgLN...",
                        "type": "text",
                        "text": {"body": "I am interested in buying the premium plan. What is the price?"}
                    }]
                }
            }]
        }]
    }
    
    # Calculate signature
    signature, body_bytes = get_signature(webhook_payload)
    
    # Send with headers
    headers = {
        "X-Hub-Signature": signature,
        "Content-Type": "application/json"
    }
    
    # Note: We pass data=body_bytes to ensure the signature matches exactly what is sent
    r = requests.post(f"{BASE_URL}/webhooks/whatsapp", data=body_bytes, headers=headers)
    print_res("Webhook Trigger", r)

    # Give the DB a split second to commit
    time.sleep(1)

    # 2. Verify Conversation Created (Module 3)
    print("\n🔹 Step 2: Verifying Conversation & NLP (Module 3)...")
    r = requests.get(f"{BASE_URL}/chat/conversations")
    print_res("List Conversations", r)
    data = r.json()
    if not data:
        print("❌ No conversations found!")
        exit()
    
    # Find the conversation for the number we just mocked (919999999999)
    convo_id = data[0]['id']
    print(f"   > Found Conversation ID: {convo_id}")

    # 3. Verify Messages & Intent (Module 3)
    r = requests.get(f"{BASE_URL}/chat/conversations/{convo_id}")
    print_res("Get Messages", r)
    msgs = r.json()
    if not msgs:
        print("❌ No messages found in conversation!")
        exit()
    
    msg_id = msgs[0]['id']
    print(f"   > Message ID: {msg_id}")
    print(f"   > Detected Intent: {msgs[0].get('intent')}")
    print(f"   > Detected Language: {msgs[0].get('language')}")

    # 4. Test Vector Embedding (Module 4)
    print("\n🔹 Step 3: Testing Vector Embedding (Module 4)...")
    r = requests.post(f"{BASE_URL}/vector/embed/{msg_id}")
    print_res("Generate Embedding", r)

    # 5. Test Similarity Search (Module 4)
    print("\n🔹 Step 4: Testing Similarity Search (Module 4)...")
    r = requests.get(f"{BASE_URL}/vector/similar", params={"text": "price of premium plan"})
    print_res("Vector Search", r)
    
    # 6. Test AI Reply Suggestion (Module 5)
    print("\n🔹 Step 5: Testing AI Reply Suggestion (Module 5)...")
    r = requests.post(f"{BASE_URL}/ai/suggest/{convo_id}")
    print_res("Generate Reply", r)
    
    suggestions = r.json()
    if suggestions:
        print("   > Suggestions:")
        for s in suggestions:
            print(f"     - {s.get('suggestion')}")
    else:
        print("   > No suggestions returned (check Cohere key?)")

if __name__ == "__main__":
    test_flow()