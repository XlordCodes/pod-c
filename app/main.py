from fastapi import FastAPI
from dotenv import load_dotenv
from api.emailer import router as emailer_router
from api.aiclient import router as llm_router
from api.webhooks import router as webhooks_router
from api.messages import router as messages_router
from api.contacts import router as contacts_router
from api.whatsapp import router as whatsapp_router

load_dotenv()

app = FastAPI()
app.include_router(emailer_router, prefix="/api/email")
app.include_router(llm_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(messages_router, prefix="/api")
app.include_router(contacts_router, prefix="/api")
app.include_router(whatsapp_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "CRM POD-C running!"}

