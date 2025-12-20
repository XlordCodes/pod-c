# app/api/aiclient.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import cohere
from app.authentication.router import get_current_user
from app.models import User
from app.core.config import settings

router = APIRouter()

class PromptRequest(BaseModel):
    prompt: str
    max_tokens: int = 100

@router.post("/generate")
def generate_text(
    request: PromptRequest,
    current_user: User = Depends(get_current_user) # Security Check
):
    """
    Direct interface to Cohere LLM.
    Requires Authentication.
    """
    if not settings.COHERE_API_KEY:
        raise HTTPException(status_code=503, detail="AI Service not configured (Missing API Key).")

    try:
        co = cohere.Client(settings.COHERE_API_KEY)
        response = co.chat(
            message=request.prompt,
            model="command-r-08-2024",
            temperature=0.7,
            max_tokens=request.max_tokens
        )
        return {"text": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))