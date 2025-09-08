# 1) Base image
FROM python:3.11-slim

# 2) Security & performance defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 3) Non-root user
RUN useradd -m appuser
WORKDIR /app

# 4) Install system dependencies (Tesseract + Indic OCR + fonts)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-mar \
    fonts-deva \
    libjpeg62-turbo \
    zlib1g \
    libc6 \
    libstdc++6 \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# 5) Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6) Copy project files into container
COPY .streamlit ./.streamlit
COPY assets ./assets
COPY agent.py ./agent.py
COPY README.md ./README.md
COPY SECURITY.md ./SECURITY.md

# 7) Environment for Tesseract
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# 8) Expose the port Streamlit will run on
EXPOSE 8501

# 9) Drop privileges
USER appuser

# 10) Run Streamlit — critical for Vercel to bind to correct port
CMD ["bash", "-lc", "streamlit run agent.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
