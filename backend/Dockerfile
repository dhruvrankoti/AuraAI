FROM python:3.10-slim

# Install system dependencies (including Tesseract OCR)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download AI models during Docker build to optimize boot time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('clip-ViT-B-32'); SentenceTransformer('all-MiniLM-L6-v2')"
RUN python -c "from facenet_pytorch import MTCNN, InceptionResnetV1; MTCNN(); InceptionResnetV1(pretrained='vggface2')"

COPY . .

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Run uvicorn on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]