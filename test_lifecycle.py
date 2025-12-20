import requests
import json
import hmac
import hashlib
import os
import time
from dotenv import load_dotenv

# 1. Load the .env file explicitly
load_dotenv()

# CONFIG
BASE_URL = "http://localhost:8000"
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")

if not APP_SECRET:
    print("❌ ERROR: Could not find WHATSAPP_APP_SECRET in .env file.")
    exit(1)

def send_webhook(event_type, payload):
    """Sends a signed POST request to your webhook endpoint."""
    
    # --- START: Serialize strictly once ---
    # We dump to a string with NO spaces (separators=(',', ':')) to match
    # what we used for the signature.
    payload_str = json.dumps(payload, separators=(',', ':'))
    payload_bytes = payload_str.encode('utf-8')
    # ------------------------------------------

    # Generate Signature from those exact bytes
    mac = hmac.new(APP_SECRET.encode(), msg=payload_bytes, digestmod=hashlib.sha256)
    sig = f"sha256={mac.hexdigest()}"
    
    headers = {"X-Hub-Signature": sig, "Content-Type": "application/json"}
    
    print(f"🔹 Sending {event_type} webhook...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/webhooks/whatsapp", 
            data=payload_bytes, 
            headers=headers
        )
        
        if resp.status_code == 200:
            print(f"✅ {event_type} Success")
        else:
            print(f"❌ {event_type} Failed: {resp.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def run_test():
    # 1. Generate a random Message ID (WAMID)
    wamid = f"wamid.HBgL{int(time.time())}"
    print(f"🚀 Starting Lifecycle Test for ID: {wamid}\n")

    # --- SCENARIO 1: Incoming Message ---
    msg_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "12345",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "1234", "phone_number_id": "1001"},
                    "messages": [{
                        "from": "919999999999",
                        "id": wamid,
                        "timestamp": str(int(time.time())),
                        "text": {"body": "Hello, is my order confirmed?"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    send_webhook("Incoming Message", msg_payload)
    time.sleep(1) # Wait for DB commit

    # --- SCENARIO 2: Status Update - SENT ---
    status_sent = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": wamid,
                        "status": "sent",
                        "timestamp": str(int(time.time())),
                        "recipient_id": "919999999999"
                    }]
                }
            }]
        }]
    }
    send_webhook("Status: SENT", status_sent)
    time.sleep(1)

    # --- SCENARIO 3: Status Update - DELIVERED ---
    status_delivered = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": wamid,
                        "status": "delivered",
                        "timestamp": str(int(time.time()))
                    }]
                }
            }]
        }]
    }
    send_webhook("Status: DELIVERED", status_delivered)
    time.sleep(1)

    # --- SCENARIO 4: Status Update - READ ---
    status_read = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": wamid,
                        "status": "read",
                        "timestamp": str(int(time.time()))
                    }]
                }
            }]
        }]
    }
    send_webhook("Status: READ", status_read)
    time.sleep(1)

    # --- SCENARIO 5: Check Dashboard ---
    print("\n📊 Checking Dashboard Metrics...")
    try:
        resp = requests.get(f"{BASE_URL}/api/status/summary")
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Dashboard Data: {json.dumps(data, indent=2)}")
            
            delivered_count = data.get("delivered", 0)
            if delivered_count > 0:
                print("\n🎉 SUCCESS: The pipeline is working! Message status tracked.")
            else:
                print("\n⚠️ WARNING: 'Delivered' count is 0. Check logic.")
        else:
            print(f"❌ Failed to fetch metrics: {resp.text}")
    except Exception as e:
        print(f"❌ Connection Error (Dashboard): {e}")

if __name__ == "__main__":
    run_test()
    