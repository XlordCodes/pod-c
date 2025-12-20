# app/api/emailer.py
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Optional
import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.models import User
from app.authentication.router import get_current_user
from app.core.config import settings

class EmailPayload(BaseModel):
    to_email: str
    subject: str
    template_name: str
    context: Optional[Dict] = {}

class Emailer:
    """A class to handle the configuration and sending of emails via SendGrid."""
    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        # Initialize SendGrid client only if API key is present
        self.sg = sendgrid.SendGridAPIClient(api_key=self.api_key) if self.api_key else None
        
        # Setup Jinja2 template environment
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
        self.template_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"])
        )

    def send_mail(self, to_email, subject, template_name, context=None, from_email=None):
        if not self.sg:
            print("⚠️ SendGrid Key missing. Email suppressed.")
            return

        if not from_email:
            from_email = settings.DEFAULT_SENDER_EMAIL
        
        template = self.template_env.get_template(template_name)
        html_content = template.render(context or {})
        
        message = Mail(
            from_email=Email(from_email),
            to_emails=[To(to_email)],
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        try:
            self.sg.send(message)
        except Exception as e:
            print(f"❌ Email Failed: {e}")

router = APIRouter()
emailer_instance = Emailer()

def get_emailer():
    return emailer_instance

@router.post("/send-email")
def send_email_handler(
    data: EmailPayload, 
    background_tasks: BackgroundTasks,
    emailer: Emailer = Depends(get_emailer),
    current_user: User = Depends(get_current_user) # Security Check
):
    """
    Sends an email in the background. Requires Auth.
    """
    background_tasks.add_task(
        emailer.send_mail,
        to_email=data.to_email,
        subject=data.subject,
        template_name=data.template_name,
        context=data.context
    )
    return {"status": "Email queued"}