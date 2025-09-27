import pytest
from app.api.emailer import send_email_handler, EmailPayload

def test_handler_returns_success_on_good_send(mocker):
    """
    Checks if the handler returns a success message when the email sends correctly.
    """
    # Arrange: Create a fake (mock) Emailer object
    mock_emailer = mocker.MagicMock()
    # Tell its send_mail method to do nothing when called
    mock_emailer.send_mail.return_value = 202

    # Arrange: Create the input data for the function
    fake_payload = EmailPayload(
        to_email="test@example.com",
        subject="Test Subject",
        template_name="dummy.html",
        context={"name": "there"}
    )

    # Act: Call the handler, passing our mock emailer in directly
    result = send_email_handler(fake_payload, emailer=mock_emailer)

    # Assert: The result should be a success status
    assert result == {"status": "Email sent"}


def test_handler_returns_error_on_failed_send(mocker):
    """
    Checks if the handler correctly catches an exception and returns an error message.
    """
    # Arrange: Create a fake (mock) Emailer object
    mock_emailer = mocker.MagicMock()
    # Tell its send_mail method to raise an error when called
    error_message = "SMTP server is down"
    mock_emailer.send_mail.side_effect = Exception(error_message)

    # Arrange: Create the input data for the function
    fake_payload = EmailPayload(
        to_email="test@example.com",
        subject="Test Subject",
        template_name="dummy.html",
        context={"name": "there"}
    )

    # Act: Call the handler, passing our mock emailer in directly
    result = send_email_handler(fake_payload, emailer=mock_emailer)

    # Assert: The result should be an error status with the correct detail
    assert result["status"] == "error"
    assert result["detail"] == error_message