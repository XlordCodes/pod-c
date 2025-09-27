import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from app.main import app

client = TestClient(app)

def test_ask_llm_success(mocker):
    mock_response = MagicMock()
    # Simulate Cohere JSON response with "text" key
    mock_response.ok = True
    mock_response.json.return_value = {"text": "module 1 test reply"}
    mocker.patch("app.api.aiclient.requests.post", return_value=mock_response)
    payload = {"prompt": "Say hi"}
    # NOTE endpoint update:
    response = client.post("/api/llm/ask", json=payload)
    assert response.status_code == 200
    assert "answer" in response.json()
    assert response.json()["answer"] == "module 1 test reply"

def test_ask_llm_failure(mocker):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mocker.patch("app.api.aiclient.requests.post", return_value=mock_response)
    payload = {"prompt": "fail test"}
    # NOTE endpoint update:
    response = client.post("/api/llm/ask", json=payload)
    assert response.status_code == 200
    assert "error" in response.json()
