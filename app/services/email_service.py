# app/services/email_service.py
import os
import logging
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- DEFINITION (Not Import) ---
class Emailer:
    """
    A class to handle the configuration and sending of emails via SendGrid.
    Moved to Services to avoid circular imports with Tasks/API.
    """
    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.sg = sendgrid.SendGridAPIClient(api_key=self.api_key) if self.api_key else None
        
        # Setup Jinja2 template environment
        # Structure: /code/app/services/email_service.py -> ../../templates
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
        
        self.template_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"])
        )

    def send_mail(self, to_email, subject, template_name, context=None, from_email=None):
        if not self.sg:
            logger.warning("⚠️ SendGrid Key missing. Email suppressed.")
            return

        if not from_email:
            from_email = settings.DEFAULT_SENDER_EMAIL
        
        try:
            # Check if template exists
            try:
                template = self.template_env.get_template(template_name)
            except Exception as e:
                logger.error(f"Template '{template_name}' not found in {self.template_env.loader.searchpath}")
                raise e

            html_content = template.render(context or {})
            
            message = Mail(
                from_email=Email(from_email),
                to_emails=[To(to_email)],
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            self.sg.send(message)
            logger.info(f"✅ Email sent to {to_email}")
            
        except Exception as e:
            logger.error(f"❌ Email Failed: {e}")
            raise e