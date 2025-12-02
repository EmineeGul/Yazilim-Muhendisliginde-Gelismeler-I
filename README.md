# Eczane Otomasyonu Projesi (Microservices)

Bu proje, **FastAPI (Backend)** ve **Flask (Frontend)** kullanılarak geliştirilmiş, Docker üzerinde çalışan mikroservis mimarili bir eczane yönetim sistemidir.

##  Proje İçeriği
* **eczane-backend:** FastAPI ile yazılmış REST API servisidir.
* **eczane-frontend:** Flask ile yazılmış web arayüzüdür.
* **docker-compose.yml:** Tüm sistemi tek komutla ayağa kaldırır.

##  Kurulum ve Çalıştırma (Docker Compose)

Projeyi en kolay şekilde çalıştırmak için terminalde proje dizinine gelip şu komutu yazmanız yeterlidir:

```bash
docker-compose up --build