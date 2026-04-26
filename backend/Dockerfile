# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# ffmpeg is required by openai-whisper for audio processing
# git is required to install whisper from GitHub
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU build separately to keep image size small (~700MB vs 2.5GB)
# This MUST be done before installing requirements.txt to satisfy openai-whisper
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir git+https://github.com/openai/whisper.git@v20240930

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
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
