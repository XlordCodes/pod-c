import requests
import os

class WhatsAppClient:
    def __init__(self, token: str = None, phone_number_id: str = None):
        self.token = token or os.environ.get("WHATSAPP_TOKEN")
        self.phone_number_id = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
        if not self.token or not self.phone_number_id:
            raise ValueError("WhatsApp API credentials are not configured.")
        self.api_url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def send_template(self, recipient_number: str, template_name: str, language_code: str = "en_US", components=None):
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            }
        }
        if components:
            payload["template"]["components"] = components

        response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=5)
        if not response.ok:
            # CRITICAL: We raise the exact JSON error text here
            raise Exception(f"[WhatsApp] API Failed. Status: {response.status_code}. Details: {response.text}")
        return response.json()

# This function is required for module compatibility and unit tests!
def send_template(to_number, template_name, language="en_US", components=None):
    try:
        client = WhatsAppClient(
            token=os.environ.get("WHATSAPP_TOKEN"),
            phone_number_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
        )
        # The client's send_template method handles the API response/failure.
        return client.send_template(to_number, template_name, language, components)
    except requests.exceptions.RequestException as e:
        # Catch network/connection errors and re-raise as a standard Exception 
        # for tenacity to catch.
        raise Exception(f"[WhatsApp Network Error] The client failed to connect to the API: {e}")