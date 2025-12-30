FROM python:3.9-slim

WORKDIR /app

# Sistem bağımlılıklarını yükle (PostgreSQL client için)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY . .

# Veritabanı tablolarını oluştur (tek satırda)
RUN python -c "from database import init_database; init_database(); print('✅ Database hazır')" || echo "⚠️ Database hatası (devam ediliyor)"

EXPOSE 8000

CMD ["uvicorn", "eczane_otomasyonu:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]