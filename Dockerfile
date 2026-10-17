FROM python:3.11-slim

WORKDIR /app

# Tizim paketlarini yangilash
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Bog'liqliklarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha kodini ko'chirish
COPY . .

# Xotira jildlari
RUN mkdir -p storage/media

VOLUME ["/app/storage"]

CMD ["python", "main.py"]
