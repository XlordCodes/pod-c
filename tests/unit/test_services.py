import pytest
from unittest.mock import MagicMock
from app.api.emailer import send_email_handler, EmailPayload
from app.integrations.whatsappclient import send_template

# --- Emailer Tests ---
def test_email_handler_success(mocker):
    # 1. Mock the Emailer Service
    mock_emailer = mocker.MagicMock()
    mock_emailer.send_mail.return_value = 202
    
    # 2. Mock BackgroundTasks (The missing argument)
    mock_bg_tasks = mocker.MagicMock()

    # 3. Create Payload
    payload = EmailPayload(
        to_email="test@test.com", 
        subject="Hi", 
        template_name="t.html", 
        context={}
    )
    
    # 4. Call Handler with ALL required arguments
    result = send_email_handler(
        payload, 
        background_tasks=mock_bg_tasks, # <--- Added this
        emailer=mock_emailer
    )
    
    # 5. Assertions
    assert result == {"status": "Email queued"}


# --- WhatsApp Tests ---
def test_whatsapp_send_success(mocker):
    # Patch the 'requests' library used inside whatsappclient
    mock_resp = mocker.Mock()
    # Simulate a successful WhatsApp API response
    mock_resp.json.return_value = {"messages": [{"id": "wamid.123"}]}
    mock_resp.raise_for_status.return_value = None
    
    # Apply the patch
    mocker.patch("app.integrations.whatsappclient.requests.post", return_value=mock_resp)
    
    # Call the function
    result = send_template("91999", "hello")
    
    # Assert
    assert result["messages"][0]["id"] == "wamid.123"