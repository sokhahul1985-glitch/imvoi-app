FROM python:3.10-slim

# Install system dependencies for OpenCV and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-khm \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements_server.txt .
RUN pip install --no-cache-dir -r requirements_server.txt

# Copy all application files
COPY . .

# Environment variable for port
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run the web server
CMD ["python", "server.py"]
