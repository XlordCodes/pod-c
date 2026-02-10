# app/core/middleware.py
import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.context import set_request_id, set_user_id, set_tenant_id
from jose import jwt, JWTError
from app.core.config import settings

logger = logging.getLogger(__name__)

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    1. Generates a unique Trace ID (X-Request-ID).
    2. Extracts User ID and Tenant ID from JWT (if present) for Audit/RLS Context.
    3. Logs request timing and status.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 1. Generate & Set Trace ID
        trace_id = str(uuid.uuid4())
        set_request_id(trace_id)
        
        # 2. Extract Context from Auth Header
        # We process this here so the Database session can pick it up immediately.
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                
                # Extract User ID
                user_id = payload.get("id")
                if user_id:
                    try:
                        set_user_id(int(user_id))
                    except (ValueError, TypeError):
                        pass

                tenant_id = payload.get("tenant_id")
                if tenant_id:
                    try:
                        set_tenant_id(int(tenant_id))
                    except (ValueError, TypeError):
                        pass

            except JWTError:
                # Auth errors are handled by the APIRouter dependencies, not here.
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