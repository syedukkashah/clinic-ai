# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=1

# Install system dependencies
# libpq-dev is required for psycopg2
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Note: PyTorch and openai-whisper have been removed from the Docker build 
# to significantly reduce image size and build time. The backend will rely
# exclusively on the cloud STT providers (Deepgram/Groq).
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel

# Copy requirements files
COPY requirements.txt .

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Default command to run the FastAPI application
# In a real deployment, you might override this for Celery workers
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1}"]
