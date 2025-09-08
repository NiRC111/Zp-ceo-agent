# 1) Base image
FROM python:3.11-slim

# 2) Safe defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 3) Create non-root user and set working directory
RUN useradd -m appuser
WORKDIR /app

# 4) System dependencies: Tesseract + OCR languages + Devanagari fonts
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

# 5) Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6) App files
COPY .streamlit ./.streamlit
COPY assets ./assets
COPY agent.py ./agent.py
COPY README.md ./README.md
COPY SECURITY.md ./SECURITY.md

# 7) Tell pytesseract where traineddata lives
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# 8) Streamlit port
EXPOSE 8501

# 9) Drop privileges
USER appuser

# 10) Start the app (Vercel provides $PORT)
CMD ["bash", "-lc", "streamlit run agent.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
