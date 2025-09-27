CRM BASE – POD C PROJECT
A modern FastAPI microservice for customer messaging, WhatsApp/Meta integration, templated email, and LLM-powered chat.

Tech Stack
Language: Python 3.11+

API Framework: FastAPI (async Python APIs)

Web Server: Uvicorn

ORM: SQLAlchemy (+ Alembic migrations)

Database: PostgreSQL (Dockerized)

HTTP: httpx, requests

Containerization: Docker, Docker Compose

Secret Mgmt: .env, python-dotenv

Email: SendGrid API + Jinja2

LLM: OpenAI API/Cohere

Testing: Pytest, pytest-mock

DevTools: VS Code, pre-commit linting

Features
WhatsApp Cloud API template-message sender

Webhook endpoint for ingestion/idempotent storage of WhatsApp messages

CRUD endpoint for Contacts (customer phonebook)

Email send endpoint (Jinja2 HTML + SendGrid)

LLM text reply endpoint (OpenAI/Cohere API)

All endpoints covered by unit and integration tests

Production/dev config via Docker Compose + .env

Folder Structure
text
crm-main/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── api/
│   │    ├── webhooks.py
│   │    ├── emailer.py
│   │    ├── aiclient.py
│   │    └── contacts.py
│   ├── integrations/
│   │    └── whatsappclient.py
│   └── templates/
│       └── invoice_email.html
├── tests/
│   ├── unit/
│   └── integration/
├── requirements.txt
├── docker-compose.yml
├── Alembic/
│   └── versions/
│       └── messages_table_update.py
└── README.md

Setup: Quick Start
1. Clone the Repo & Install Requirements
bash
git clone <repo>
cd crm-main
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
2. Create .env file
text
DATABASE_URL=postgresql://postgres:username@db:5432/crm_main
SENDGRID_API_KEY=your_sendgrid_key
DEFAULT_SENDER_EMAIL=your@email.com
COHERE_API_KEY=your_cohere_key
WHATSAPP_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_APP_SECRET=your_app_secret
Never commit .env or share secrets in public repos.

3. Start Services and Run Migrations
bash
docker compose up -d
docker compose exec app alembic upgrade head  # run migrations inside the app container
4. Run the App
bash
docker compose exec app uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
App docs live at:
http://localhost:8000/docs

API Endpoints
WhatsApp
Send Template:
POST /whatsapp/send-template
JSON: {"to": "<recipient>", "template": "<template_name>", ...}

Receive Webhook:
POST /webhooks/whatsapp
Meta-signed webhook events (HMAC with WHATSAPP_APP_SECRET).

Contacts (CRUD)
POST /contacts/

GET /contacts/{id}

PUT /contacts/{id}

DELETE /contacts/{id}

Email
POST /send-email
JSON: {"to_email":"abc@example.com", "subject":"Hi", "template_name":"invoice_email.html", "context":{"name":"Alice"}}

LLM
POST /llm/ask
JSON: {"prompt": "What's the weather like?"}

Testing
Run all tests
bash
pytest
Run integration tests
bash
pytest tests/integration/
Unit tests mock all external HTTP/DB as needed.

Example Requests (curl)
Send WhatsApp Template:

bash
curl -X POST http://localhost:8000/whatsapp/send-template \
  -H "Content-Type: application/json" \
  -d '{"to": "+911234567890", "template": "hello_world"}'
POST Webhook (Dev only):

bash
curl -X POST http://localhost:8000/webhooks/whatsapp \
  -H "X-Hub-Signature: <computed_signature>" \
  -d '{"entry": [{"changes": [{"value": {"messages": [{"from": "91...", "id": "msgid", "text": {"body": "test"}}], "metadata": {"phone_number_id": "..."}}}]}]}'
Send Email:

bash
curl -X POST http://localhost:8000/send-email \
  -H "Content-Type: application/json" \
  -d '{"to_email": "you@example.com", "subject": "Test", "template_name": "invoice_email.html", "context": {"name": "User"}}'
LLM Prompt:

bash
curl -X POST http://localhost:8000/llm/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello in French"}'


Dev & Security Notes
Make sure your .env is in .gitignore!

Use HTTPS and rotate tokens in production.

Logs DO NOT contain sensitive .env values.

Authors & License
CRM Team, 2025
