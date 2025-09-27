import pytest
from app.integrations.whatsappclient import send_template

def test_send_template_success(mocker):
    # Mock requests.post to simulate WhatsApp API call
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"messages": [{"id": "wamid.12345"}]}
    mock_response.raise_for_status.return_value = None
    mocker.patch("app.integrations.whatsappclient.requests.post", return_value=mock_response)

    result = send_template("919444285541", "hello_world")
    assert "messages" in result
    assert result["messages"][0]["id"] == "wamid.12345"

