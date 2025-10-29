# Start with Python 3.10 slim (smaller, faster)
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install system libraries
# curl - needed for Coolify health checks
# libgl1 - OpenGL library (for image processing)
# libglib2.0-0 - GLIB library (core utilities)
# libgomp1 - GNU OpenMP (for parallel processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Tell Docker this app uses port 8080
EXPOSE 8080

# Health check configuration for Docker
# This tells Docker how to check if the container is healthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Command to run when container starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
