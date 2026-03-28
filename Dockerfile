FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# System packages for OpenCV + Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Streamlit config inside container
RUN mkdir -p /app/.streamlit && printf "[server]\nshowEmailPrompt = false\nheadless = true\naddress = \"0.0.0.0\"\nport = 8503\n\n[browser]\ngatherUsageStats = false\n" > /app/.streamlit/config.toml

EXPOSE 8503

CMD ["streamlit", "run", "app_streamlit.py", "--server.address=0.0.0.0", "--server.port=8503"]
