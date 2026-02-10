# app/api/aiclient.py
"""
Module: AI Client API
Context: Pod C - AI Access

Direct interface to the LLM provider (OpenAI).
Used for ad-hoc generation tasks not covered by specific services.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from openai import OpenAI
from app.authentication.router import get_current_user
from app.models import User
from app.core.config import settings

router = APIRouter()

class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_tokens: int = Field(150, ge=10, le=500)

@router.post("/generate")
def generate_text(
    request: PromptRequest,
    current_user: User = Depends(get_current_user) # Security Check
):
    """
    Direct interface to OpenAI GPT.
    Requires Authentication.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="AI Service not configured (Missing API Key).")

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful CRM assistant."},
                {"role": "user", "content": request.prompt}
            ],
            max_tokens=request.max_tokens,
            temperature=0.7
        )
        
        return {"text": response.choices[0].message.content.strip()}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Provider Error: {str(e)}")