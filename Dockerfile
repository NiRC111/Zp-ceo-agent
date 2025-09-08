FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd -m appuser
WORKDIR /app

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-mar \
    fonts-deva \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .streamlit ./.streamlit
COPY assets ./assets
COPY agent.py ./agent.py
COPY README.md ./README.md
COPY SECURITY.md ./SECURITY.md
COPY vercel.json ./vercel.json

EXPOSE 8501
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
USER appuser

CMD ["bash", "-lc", "streamlit run agent.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
