import os
import requests
from fastapi import APIRouter
from pydantic import BaseModel

class CohereClient:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise RuntimeError("Cohere API key is missing!")
        self.model = model or "command-r-08-2024"
        self.url = f"https://api.cohere.ai/v1/chat"

    def call_llm(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "message": prompt,
        }
        response = requests.post(self.url, headers=headers, json=data)
        if not response.ok:
            raise Exception(f"[Cohere] Failed: {response.status_code} {response.text}")
        try:
            return response.json()["text"]
        except Exception:
            raise ValueError(f"Bad Completion: {response.text}")

router = APIRouter()
cohere_client = CohereClient()

class PromptRequest(BaseModel):
    prompt: str

@router.post("/llm/ask")
def ask_llm(data: PromptRequest):
    try:
        answer = cohere_client.call_llm(data.prompt)
        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}