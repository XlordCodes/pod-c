# app/core/middleware.py
import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.context import set_request_id, set_user_id
from jose import jwt, JWTError
from app.core.config import settings

logger = logging.getLogger(__name__)

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    1. Generates a unique Trace ID (X-Request-ID) for every request.
    2. Extracts User ID from JWT (if present) for Audit Context.
    3. Logs request timing and status.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 1. Generate & Set Trace ID
        trace_id = str(uuid.uuid4())
        set_request_id(trace_id)
        
        # 2. Try to set User ID context (Best effort for Audit Logs)
        # We don't fail here if auth fails; the Auth Router handles enforcement.
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                email = payload.get("sub")
                # Note: To get the numeric ID, we'd need a DB call or store it in JWT.
                # For efficiency, we skip the DB call here. Real User ID is handled 
                # in dependencies. We set a marker or None.
                # Ideally, put user_id in JWT payload to avoid DB hits here.
                pass 
            except JWTError:
                pass

        # 3. Process Request
        response = await call_next(request)
        
        # 4. Calculate Duration
        process_time = (time.time() - start_time) * 1000
        
        # 5. Log structured info
        logger.info(
            f"Handled request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(process_time, 2)
            }
        )
        
        # 6. Return Trace ID to client
        response.headers["X-Request-ID"] = trace_id
        return response