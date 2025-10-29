# Start with Python 3.10 slim (smaller, faster)
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install system libraries that OpenCV and PaddlePaddle need
# libgl1 - OpenGL library (for image processing)
# libglib2.0-0 - GLIB library (core utilities)
# libgomp1 - GNU OpenMP (for parallel processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Command to run when container starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
