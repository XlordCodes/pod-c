from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Optional
import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader, select_autoescape

class EmailPayload(BaseModel):
    to_email: str
    subject: str
    template_name: str
    context: Optional[Dict] = {}

class Emailer:
    """A class to handle the configuration and sending of emails via SendGrid."""
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("SENDGRID_API_KEY")
        if not self.api_key:
            raise RuntimeError("SendGrid API key is missing!")
        self.sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
        
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
        self.template_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"])
        )

    def send_mail(self, to_email, subject, template_name, context=None, from_email=None):
        """Builds and sends an email using a specified HTML template."""
        if not from_email:
            from_email = os.environ.get("DEFAULT_SENDER_EMAIL", "noreply@example.com")
        
        template = self.template_env.get_template(template_name)
        html_content = template.render(context or {})
        
        message = Mail(
            from_email=Email(from_email),
            to_emails=[To(to_email)],
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        response = self.sg.send(message)
        
        # Raise an exception for any non-successful status codes (4xx or 5xx)
        if response.status_code >= 400:
            raise Exception(f"Failed to send email: {response.status_code} {response.body.decode()}")
        
        return response.status_code

router = APIRouter()
# A single instance of Emailer is created for the application to use
emailer_instance = Emailer()

def get_emailer():
    """Dependency provider function for the Emailer instance."""
    return emailer_instance

def send_email_handler(data: EmailPayload, emailer: Emailer = Depends(get_emailer)):
    """
    FastAPI endpoint handler that sends an email and returns the status.
    It uses a try/except block to gracefully handle any failures.
    """
    try:
        emailer.send_mail(
            to_email=data.to_email,
            subject=data.subject,
            template_name=data.template_name,
            context=data.context,
        )
        return {"status": "Email sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

router.post("/send-email")(send_email_handler)