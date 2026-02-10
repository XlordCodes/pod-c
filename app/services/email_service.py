# app/services/email_service.py
"""
Module: Email Service
Context: Pod C - Notifications

Handles transactional email delivery via SendGrid.
Includes Jinja2 template rendering and automatic retries for API resilience.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader, select_autoescape
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from python_http_client.exceptions import HTTPError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Resolve paths robustly
# logic: app/services/email_service.py -> app/services -> app -> root -> templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"

class Emailer:
    """
    Singleton-style service for handling email dispatch.
    """
    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        # If no key is configured, we simply log warnings instead of crashing.
        self.client = sendgrid.SendGridAPIClient(api_key=self.api_key) if self.api_key else None
        
        # Initialize Jinja2
        self.template_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"])
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HTTPError, ConnectionError))
    )
    def send_mail(
        self, 
        to_email: str, 
        subject: str, 
        template_name: str, 
        context: Optional[Dict[str, Any]] = None, 
        from_email: Optional[str] = None
    ):
        """
        Renders a template and sends an email via SendGrid.
        """
        if not self.client:
            logger.warning(f"⚠️ SendGrid API Key missing. Email to {to_email} suppressed.")
            return

        sender = from_email or settings.DEFAULT_SENDER_EMAIL or "noreply@example.com"
        
        try:
            # 1. Render Template
            template = self.template_env.get_template(template_name)
            html_content = template.render(context or {})
            
            # 2. Construct Message
            message = Mail(
                from_email=Email(sender),
                to_emails=[To(to_email)],
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            # 3. Send (with Retry)
            response = self.client.send(message)
            
            if response.status_code not in (200, 201, 202):
                raise HTTPError(response.status_code, "SendGrid refused the request", response.body, response.headers)
                
            logger.info(f"✅ Email sent to {to_email} (Template: {template_name})")
            
        except Exception as e:
            logger.error(f"❌ Email Failed to {to_email}: {str(e)}")
            raise # Re-raise to trigger Tenancy retry