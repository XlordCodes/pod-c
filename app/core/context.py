# app/core/context.py
from contextvars import ContextVar
from typing import Optional

# Context variables to store state during a request lifecycle
request_id_ctx: ContextVar[str] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar("user_id", default=None)

def get_request_id() -> str:
    return request_id_ctx.get()

def set_request_id(request_id: str):
    request_id_ctx.set(request_id)

def get_user_id() -> Optional[int]:
    return user_id_ctx.get()

def set_user_id(user_id: int):
    user_id_ctx.set(user_id)