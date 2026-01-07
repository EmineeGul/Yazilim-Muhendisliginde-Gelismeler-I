
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


sequenceDiagram
    participant U as Kullanıcı (Frontend)
    participant A as Auth Servisi (JWT)
    participant B as Backend API
    participant D as PostgreSQL

    U->>A: Login (Username/Password)
    A-->>U: JWT Token Döndür
    U->>B: GET /drugs (Bearer Token ile)
    B->>B: Token Doğrulama
    B->>D: SELECT * FROM drugs
    D-->>B: İlaç Listesi
    B-->>U: JSON Verisi (200 OK)
