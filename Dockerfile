# Use a slim python image to reduce surface area
FROM python:3.11-slim

# Set environment variables for Python and HuggingFace cache
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/huggingface

WORKDIR /code

# Install system build dependencies
# We clean up apt lists afterwards to keep the layer small
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
# --no-cache-dir reduces image size
# timeout=100 helps with slow downloads for PyTorch
RUN pip install --no-cache-dir --timeout=100 -r requirements.txt

# Copy application code
COPY . /code

# Start the application server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]