from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
import datetime

app = FastAPI(
    title="Eczane Otomasyonu API",
    version="1.0.0",
    description="Eczane ilaç, stok ve satış yönetimi için API"
)

# --- CORS İzinleri ---
# (Frontend'in bağlanabilmesi için DersYoldaşı örneğindeki gibi)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MOCK VERİTABANI ---
# Veriler sunucu yeniden başladığında sıfırlanır.

# Personel (Kullanıcı) Veritabanı
# Roller: Yonetici, Personel (Sequence diagramına göre)
personnel_db = [
    {
        "id": "admin_1",
        "username": "yonetici",
        "password": "admin123", # ÖNEMLİ: Şifreler asla böyle saklanmamalı!
        "full_name": "Selin Yönetici",
        "role": "Yonetici"
    },
    {
        "id": "user_1",
        "username": "personel",
        "password": "user123",
        "full_name": "Ahmet Personel",
        "role": "Personel"
    }
]

# İlaç Veritabanı
drugs_db = [
    {
        "id": "drug_1",
        "name": "Parol",
        "description": "Ağrı kesici",
        "price": 50.75,
        "stock_quantity": 100,
        "low_stock_threshold": 20 # Düşük stok sınırı
    },
    {
        "id": "drug_2",
        "name": "Nurofen",
        "description": "Ağrı kesici",
        "price": 80.00,
        "stock_quantity": 15, # Düşük stokta!
        "low_stock_threshold": 20
    }
]

# Satış Kayıtları Veritabanı
sales_db = []

# --- MODELLER (Pydantic) ---

# 1. Giriş Modelleri
class PersonnelLogin(BaseModel):
    username: str
    password: str

class PersonnelInfo(BaseModel):
    id: str
    username: str
    full_name: str
    role: str

# 2. İlaç ve Stok Modelleri
class DrugBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock_quantity: int

class DrugCreate(DrugBase):
    low_stock_threshold: int = 10 # Opsiyonel, varsayılanı 10

class Drug(DrugBase):
    id: str
    low_stock_threshold: int

# 3. Satış Modelleri
class SaleCreate(BaseModel):
    drug_id: str
    quantity: int

class Sale(BaseModel):
    id: str
    drug_id: str
    quantity_sold: int
    total_price: float
    timestamp: datetime.datetime

# --- GÜVENLİK ve YETKİLENDİRME ---
# (Sequence diagramındaki roller için basit bir sistem)

auth_scheme = HTTPBearer()

# Token'dan kullanıcıyı bulan (sahte) fonksiyon
async def get_current_user(token: HTTPAuthorizationCredentials = Security(auth_scheme)):
    # Token'ı "fake-token-for-{id}-role-{role}" formatında bekliyoruz
    try:
        token_str = token.credentials
        if not token_str.startswith("fake-token-for-"):
            raise HTTPException(status_code=401, detail="Geçersiz token formatı")
        
        parts = token_str.split("-")
        user_id = parts[3]
        user_role = parts[5]

        # Kullanıcıyı DB'de bul
        user = next((p for p in personnel_db if p["id"] == user_id and p["role"] == user_role), None)
        
        if not user:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı veya token geçersiz")
        
        return user # Kullanıcının tüm bilgilerini dict olarak döndür
    except Exception:
        raise HTTPException(status_code=401, detail="Token ayrıştırılamadı veya geçersiz")

# Sadece Yöneticilerin erişebileceği endpoint'ler için dependency
async def get_admin_user(current_user: dict = Depends(get_current_user)):
    """
    Mevcut kullanıcının rolünün "Yonetici" olup olmadığını kontrol eder.
    Değilse 403 Forbidden hatası fırlatır.
    """
    if current_user["role"] != "Yonetici":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlemi yapmak için yönetici yetkisi gereklidir."
        )
    return current_user


# --- ENDPOINT'LER ---

@app.get("/")
async def root():
    return {"mesaj": "Eczane Otomasyonu API'sine hoş geldiniz!"}

# --- 1. GİRİŞ İŞLEMLERİ ---
# (Sequence Diagram 1)

@app.post("/login", status_code=status.HTTP_200_OK)
async def login(creds: PersonnelLogin):
    """
    Kullanıcı adı ve şifre ile giriş yapar.
    Başarılı olursa, rol ve ID içeren sahte bir token döndürür.
    """
    # (Backend ->> DB: Kullanıcı kontrolü)
    user = next((p for p in personnel_db if p["username"] == creds.username and p["password"] == creds.password), None)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre"
        )
    
    # (Backend -->> UI: Rol belirlenir)
    # Token, yetkilendirme (authorization) için rol bilgisini de içermeli.
    token = f"fake-token-for-{user['id']}-role-{user['role']}"
    
    user_info = PersonnelInfo(**user)
    
    return {
        "mesaj": "Giriş başarılı",
        "token": token,
        "user_info": user_info 
    }

# --- 2. İLAÇ VE STOK YÖNETİMİ ---
# (Sequence Diagram 2)

@app.get("/drugs", response_model=List[Drug])
async def get_all_drugs(current_user: dict = Depends(get_current_user)):
    """
    (Personel/Yönetici) Tüm ilaçları ve stok durumlarını listeler.
    """
    # (Personel ->> UI: Stok görüntüle ->> Backend: Stok isteği)
    return drugs_db

@app.get("/drugs/low-stock", response_model=List[Drug])
async def get_low_stock_drugs(current_user: dict = Depends(get_current_user)):
    """
    (Personel/Yönetici) Sadece stoğu kritik seviyenin altında olan ilaçları listeler.
    """
    # (Backend ->> UI: Düşük stok uyarısı)
    low_stock_list = [
        drug for drug in drugs_db 
        if drug['stock_quantity'] <= drug['low_stock_threshold']
    ]
    
    # (Backend ->> Depo: Sipariş gönder - Simülasyon)
    if low_stock_list:
        print(f"SİSTEM UYARISI: {len(low_stock_list)} kalem ilaç düşük stokta. Depoya sipariş gönderiliyor...")
        
    return low_stock_list

@app.post("/drugs", response_model=Drug, status_code=status.HTTP_201_CREATED)
async def create_drug(drug: DrugCreate, admin_user: dict = Depends(get_admin_user)):
    """
    (Yönetici) Sisteme yeni bir ilaç ekler.
    Sadece 'Yonetici' rolündeki kullanıcılar erişebilir.
    """
    # (Yonetici ->> UI: İlaç yönetimi ekranı ->> Backend: İlaç bilgileri)
    
    new_drug_data = drug.dict()
    new_drug_data["id"] = str(uuid4())
    
    # Pydantic modelini dict'e çevirip DB'ye ekliyoruz (Mock DB için)
    drugs_db.append(new_drug_data)
    
    # (Backend ->> DB: Ekle)
    return new_drug_data

@app.put("/drugs/{drug_id}", response_model=Drug)
async def update_drug(drug_id: str, drug_update: DrugCreate, admin_user: dict = Depends(get_admin_user)):
    """
    (Yönetici) Mevcut bir ilacın bilgilerini (fiyat, stok vb.) günceller.
    Sadece 'Yonetici' rolündeki kullanıcılar erişebilir.
    """
    drug = next((d for d in drugs_db if d['id'] == drug_id), None)
    
    if not drug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlaç bulunamadı")
    
    # (Backend ->> DB: Güncelle)
    # Gelen veriyi (drug_update) mevcut veri (drug) üzerine yaz
    update_data = drug_update.dict()
    drug.update(update_data)
    
    return drug

@app.delete("/drugs/{drug_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drug(drug_id: str, admin_user: dict = Depends(get_admin_user)):
    """
    (Yönetici) Sistemden bir ilacı siler.
    Sadece 'Yonetici' rolündeki kullanıcılar erişebilir.
    """
    global drugs_db
    drug = next((d for d in drugs_db if d['id'] == drug_id), None)
    
    if not drug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlaç bulunamadı")
    
    drugs_db = [d for d in drugs_db if d['id'] != drug_id]
    return


# --- 3. SATIŞ İŞLEMLERİ ---
# (Sequence Diagram 3)

@app.post("/sales", response_model=Sale, status_code=status.HTTP_201_CREATED)
async def make_sale(sale: SaleCreate, current_user: dict = Depends(get_current_user)):
    """
    (Personel/Yönetici) Bir ilaç satışı gerçekleştirir.
    Stoktan düşer ve satış kaydı oluşturur.
    """
    # (Personel ->> UI: Satış başlat ->> Backend: Ürün bilgisi)
    drug = next((d for d in drugs_db if d['id'] == sale.drug_id), None)

    if not drug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Satılmak istenen ilaç bulunamadı")

    if drug['stock_quantity'] < sale.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Yetersiz stok. Kalan: {drug['stock_quantity']}, İstenen: {sale.quantity}"
        )

    # (Backend ->> DB: Stok güncelle)
    drug['stock_quantity'] -= sale.quantity
    
    total_price = drug['price'] * sale.quantity
    
    # (Backend ->> ITS: Reçete veya satış bildirimi - Simülasyon)
    print(f"ITS BİLDİRİMİ: {drug['name']} adlı ilaçtan {sale.quantity} adet satıldı.")

    # (Backend ->> DB: Satış kaydı)
    new_sale = Sale(
        id=str(uuid4()),
        drug_id=sale.drug_id,
        quantity_sold=sale.quantity,
        total_price=total_price,
        timestamp=datetime.datetime.now()
    )
    
    # Modeli dict'e çevirip mock DB'ye ekliyoruz
    sales_db.append(new_sale.dict())
    
    # (Backend -->> UI: Satış tamamlandı)
    return new_sale

@app.get("/sales", response_model=List[Sale])
async def get_sales_history(admin_user: dict = Depends(get_admin_user)):
    """
    (Yönetici) Tüm satış geçmişini listeler.
    Sadece 'Yonetici' rolündeki kullanıcılar erişebilir.
    """
    return sales_db


# --- Çalıştırma Komutu ---
# Bu dosyayı main.py olarak kaydet ve terminalde şunu çalıştır:
# uvicorn main:app --reload
#
# Swagger dokümantasyonu için: http://127.0.0.1:8000/docs
# OpenAPI JSON dosyası için: http://127.0.0.1:8000/openapi.json