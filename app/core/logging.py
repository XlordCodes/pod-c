# app/core/logging.py
import logging
import sys
import json
from app.core.context import get_request_id, get_user_id

class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    Injects Correlation IDs (trace_id) and User IDs automatically.
    """
    def format(self, record):
        log_record = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "trace_id": get_request_id(), # <--- Auto-injected
            "user_id": get_user_id(),     # <--- Auto-injected
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def configure_logging():
    """
    Configures the root logger to output JSON to stdout.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    if root_logger.handlers:
        root_logger.handlers = []

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    
    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)