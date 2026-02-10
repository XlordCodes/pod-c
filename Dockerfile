# Use a slim python image to reduce surface area
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/huggingface

WORKDIR /code

# 1. Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=100 -r requirements.txt

# 3. Setup Entrypoint (The Traffic Controller)
COPY entrypoint.sh .

# CRITICAL FIX FOR WINDOWS USERS:
# This removes Windows-style line endings (\r) so the script runs on Linux
RUN sed -i 's/\r$//' /code/entrypoint.sh

# Make it executable
RUN chmod +x /code/entrypoint.sh

# 4. Copy application code
COPY . /code

# 5. Define the entrypoint
# This script will wait for the DB, run migrations, then start the app
ENTRYPOINT ["/code/entrypoint.sh"]

# 6. Default Command (can be overridden by docker-compose for celery)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]