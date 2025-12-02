FROM python:3.9-slim

WORKDIR /app

COPY . /app

# Schedule bağımlılığını ekle
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install fastapi uvicorn pydantic schedule python-decouple

EXPOSE 8000

CMD ["uvicorn", "eczane_otomasyonu:app", "--host", "0.0.0.0", "--port", "8000"]