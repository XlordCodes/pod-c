import pytest
from fastapi.testclient import TestClient
from app.main import app
import requests

client = TestClient(app)

def test_llm_ask_success(mocker):
    # Arrange: Patch requests.post to simulate a successful response from Cohere API
    mock_response = mocker.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"text": "Hello world!"}
    mocker.patch("requests.post", return_value=mock_response)

    # Act: Post to the FastAPI endpoint with a sample prompt
    payload = {"prompt": "Say hello"}
    response = client.post("/api/llm/ask", json=payload)

    # Assert: Should return the mocked answer
    assert response.status_code == 200
    assert response.json()["answer"] == "Hello world!"

def test_llm_ask_api_error(mocker):
    mock_response = mocker.Mock()
    mock_response.ok = False
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mocker.patch("requests.post", return_value=mock_response)

    payload = {"prompt": "fail test"}
    response = client.post("/api/llm/ask", json=payload)
    assert response.status_code == 200
    assert "error" in response.json()
    assert "[Cohere] Failed: 404" in response.json()["error"]
