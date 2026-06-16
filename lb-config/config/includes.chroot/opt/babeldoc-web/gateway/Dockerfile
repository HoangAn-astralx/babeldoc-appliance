FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps that babeldoc / onnxruntime may need at runtime.
# tesseract-ocr (+ language packs) powers the scanned-page text-layer fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 fontconfig \
    tesseract-ocr \
    tesseract-ocr-eng tesseract-ocr-vie tesseract-ocr-chi-sim \
    tesseract-ocr-jpn tesseract-ocr-kor tesseract-ocr-fra \
    tesseract-ocr-deu tesseract-ocr-spa tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

# PyMuPDF's get_textpage_ocr() locates Tesseract language data via this env.
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

COPY requirements.txt .
RUN pip install -r requirements.txt && pip install babeldoc

# In Docker the runner uses the image's own python.
ENV BABELDOC_RUN_CMD=python \
    DATA_DIR=/data

COPY . .

# Pre-download babeldoc offline assets so first request is fast.
RUN python -c "import babeldoc.format.pdf.high_level as h; h.init()" || true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
