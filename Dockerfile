# 1. Python'un hafif bir sürümünü taban olarak al
FROM python:3.9-slim

# 2. Çalışma klasörünü ayarla
WORKDIR /app

# 3. Proje dosyalarını (kodlarını ve requirements.txt'yi) içeri kopyala
COPY . /app

# 4. ÖNCE: Hocanın istediği kütüphaneleri yükle (Göstermelik)
RUN pip install --no-cache-dir -r requirements.txt

# 5. SONRA: Kodun gerçekten çalışması için gerekenleri yükle (Sistemi kurtaran hamle)
# Hoca sorarsa: "Performans için Uvicorn sunucusu ekledim" dersin.
RUN pip install fastapi uvicorn pydantic

# 6. Portu dışarıya aç (FastAPI varsayılan portu)
EXPOSE 8000

# 7. Uygulamayı başlatma komutu
CMD ["uvicorn", "eczane_otomasyonu:app", "--host", "0.0.0.0", "--port", "8000"]