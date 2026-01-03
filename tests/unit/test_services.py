# tests/unit/test_services.py
import pytest
from unittest.mock import MagicMock

from app.services.email_service import Emailer
from app.api.emailer import send_email_handler, EmailPayload

from app.integrations.whatsapp_client import send_template

# --- 1. Test the API Handler (Queuing Logic) ---
def test_email_handler_queues_job(mocker):
    """
    Test that the handler creates a DB record (EmailQueue) instead of sending immediately.
    """
    # 1. Mock Database Session
    mock_db = mocker.MagicMock()
    
    # Define behavior for db.refresh so the object gets an ID
    def side_effect_refresh(obj):
        obj.id = 123
    mock_db.refresh.side_effect = side_effect_refresh

    # 2. Mock Current User (Required by dependency)
    mock_user = mocker.MagicMock()
    mock_user.id = 1

    # 3. Create Payload
    payload = EmailPayload(
        to_email="test@test.com", 
        subject="Welcome", 
        template_name="welcome.html", 
        context={"name": "Test"}
    )

    # The handler calls send_email_task.delay(id)
    mock_task = mocker.patch("app.api.emailer.send_email_task")

    # 4. Call Handler
    result = send_email_handler(
        data=payload, 
        db=mock_db, 
        current_user=mock_user
    )

    # 5. Assertions
    # Verify the API response
    assert result["status"] == "queued"
    assert result["job_id"] == 123
    
    # Verify DB interactions
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    
    # Verify task dispatch
    mock_task.delay.assert_called_once_with(123)
    
    # Verify what was actually added to the DB
    args, _ = mock_db.add.call_args
    queued_item = args[0]
    
    # Check attributes of the EmailQueue object
    assert queued_item.to_email == "test@test.com"
    assert queued_item.status == "pending"
    assert queued_item.template_name == "welcome.html"


# --- 2. Test the Emailer Class (Worker Logic) ---
def test_emailer_sends_via_sendgrid(mocker):
    """
    Test the Emailer class separately. 
    This mocks SendGrid and Jinja2 to ensure the .send_mail() method works.
    """
    
    # 1. Mock external dependencies to prevent file/network errors
    mocker.patch("app.services.email_service.FileSystemLoader") 
    mocker.patch("app.services.email_service.settings.SENDGRID_API_KEY", "fake_key")
    
    # 2. Mock SendGrid Client
    mock_sg_client = mocker.Mock()
    mocker.patch("app.services.email_service.sendgrid.SendGridAPIClient", return_value=mock_sg_client)
    
    # 3. Mock Jinja2 Environment
    # We want to mock the .get_template().render() chain
    mock_env_cls = mocker.patch("app.services.email_service.Environment")
    mock_env_instance = mock_env_cls.return_value
    
    mock_template = mocker.Mock()
    mock_template.render.return_value = "<html>Hello World</html>"
    mock_env_instance.get_template.return_value = mock_template

    # 4. Instantiate Emailer
    emailer = Emailer()
    
    # 5. Call send_mail
    emailer.send_mail(
        to_email="customer@example.com",
        subject="Hello",
        template_name="test.html"
    )

    # 6. Assertions
    # Verify template was rendered
    mock_template.render.assert_called_once()
    # Verify SendGrid's .send() was called
    mock_sg_client.send.assert_called_once()


# --- 3. WhatsApp Tests (Existing) ---
def test_whatsapp_send_success(mocker):
    """
    Test the WhatsApp client wrapper.
    """
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"messages": [{"id": "wamid.123"}]}
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    
    mocker.patch("app.integrations.whatsapp_client.requests.post", return_value=mock_resp)
    
    result = send_template("9199999999", "hello_world_template")
    assert result["messages"][0]["id"] == "wamid.123"