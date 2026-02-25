# app/seeds/seed_analytics.py
"""
Module: Analytics Seeder
Context: Pod B - Module 6 (Data Fixtures)

Simulates WhatsApp webhook traffic to populate analytics data.
Requires the API server to be running at localhost:8000.

ERROR HANDLING:
    - Any failure triggers a clear error message and non-zero exit
    - Network errors are not silently swallowed
"""

import sys
import requests
import json
import hmac
import hashlib
import time
import random
from dotenv import load_dotenv

# Import settings to access the WhatsApp app secret
from app.core.config import settings

# Load Config
load_dotenv()
BASE_URL = "http://localhost:8000"

# Test Data: (Phone, Message, Expected Sentiment)
TEST_DATA = [
    ("919000000001", "I absolutely love this product! It's amazing.", "positive"),
    ("919000000002", "This is the worst service I have ever used. Terrible.", "negative"),
    ("919000000003", "Can you tell me your opening hours?", "neutral"),
    ("919000000004", "I am very happy with the quick delivery.", "positive"),
    ("919000000005", "My order is broken and nobody is replying.", "negative"),
    ("919000000006", "What is the price of the premium plan?", "neutral"),
    ("919000000007", "Excellent support team, thank you!", "positive"),
]


def send_signed_webhook(payload):
    """
    Sends payload with valid HMAC signature.
    
    Uses the WhatsApp app secret from settings to ensure the signature
    matches what the backend expects.
    
    Args:
        payload (dict): The webhook payload to send.
        
    Raises:
        requests.RequestException: On network or HTTP errors.
    """
    payload_str = json.dumps(payload, separators=(',', ':'))
    payload_bytes = payload_str.encode('utf-8')
    
    # Use settings.WHATSAPP_APP_SECRET directly to match the backend
    mac = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(), 
        msg=payload_bytes, 
        digestmod=hashlib.sha256
    )
    
    headers = {
        "X-Hub-Signature-256": f"sha256={mac.hexdigest()}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/v1/api/webhooks/whatsapp", 
        data=payload_bytes, 
        headers=headers,
        timeout=10
    )
    response.raise_for_status()


def run_simulation():
    """
    Main execution function for analytics seeding.
    
    Sends simulated WhatsApp messages to populate the analytics dashboard.
    
    Raises:
        Exception: Re-raises any error for caller to handle.
    """
    print(f"🚀 Starting Data Seeding for {len(TEST_DATA)} conversations...")
    
    generated_wamids = []

    try:
        # 1. Loop through data and create conversations
        for phone, text, sentiment in TEST_DATA:
            wamid = f"wamid.SEED.{random.randint(1000, 9999)}"
            generated_wamids.append(wamid)
            
            print(f"   -> Msg from {phone}: '{text[:30]}...' ({sentiment})")
            
            # A. Incoming Message
            msg_payload = {
                "entry": [{
                    "changes": [{
                        "value": {
                            "messages": [{
                                "from": phone,
                                "id": wamid,
                                "type": "text",
                                "text": {"body": text},
                                "timestamp": str(int(time.time()))
                            }]
                        }
                    }]
                }]
            }
            send_signed_webhook(msg_payload)
            
            # B. Lifecycle Updates (Simulate network delay)
            # Status: SENT
            send_signed_webhook({
                "entry": [{
                    "changes": [{
                        "value": {
                            "statuses": [{
                                "id": wamid,
                                "status": "sent",
                                "recipient_id": phone,
                                "timestamp": str(int(time.time()))
                            }]
                        }
                    }]
                }]
            })
            
            # Status: DELIVERED
            send_signed_webhook({
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
            })
            
            # Status: READ (Only read 50% of them to make stats realistic)
            if random.choice([True, False]):
                send_signed_webhook({
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
                })
                
        print("\n⏱️  Simulating 'Avg Response Time' (Adding 2nd msg for User 1)...")
        # Add a 2nd message for the first user to create a "Time Gap" for the analytics view
        time.sleep(2) # Wait 2 seconds so the gap is measurable
        
        wamid_2 = "wamid.SEED.SECOND"
        phone_1 = TEST_DATA[0][0]
        msg_2 = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": phone_1,
                            "id": wamid_2,
                            "type": "text",
                            "text": {"body": "Also, do you have a discount?"},
                            "timestamp": str(int(time.time()))
                        }]
                    }
                }]
            }]
        }
        send_signed_webhook(msg_2)
        print("   -> 2nd Msg sent.")

        print("\n✅ Seeding Complete. Check Swagger UI!")
        
    except requests.RequestException as e:
        print(f"❌ Network Error: {str(e)}")
        raise
    except Exception as e:
        print(f"❌ Seeding Failed: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        run_simulation()
    except Exception:
        sys.exit(1)
