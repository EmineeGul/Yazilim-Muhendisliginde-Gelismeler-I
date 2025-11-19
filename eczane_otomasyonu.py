from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import random  # İTS ve Depo simülasyonu için

app = FastAPI()

# --- VERİTABANI (Simülasyon) ---
users_db = {
    "yonetici": {"password": "admin123", "role": "Yönetici"},
    "personel": {"password": "123", "role": "Personel"}
}

drugs_db = [
    {"id": 1, "name": "Parol", "active_ingredient": "Parasetamol", "price": 50.0, "stock_quantity": 100, "description": "Ağrı kesici"},
    {"id": 2, "name": "Majezik", "active_ingredient": "Flurbiprofen", "price": 85.0, "stock_quantity": 20, "description": "Anti-enflamatuar"},
    {"id": 3, "name": "Aspirin", "active_ingredient": "Asetilsalisilik Asit", "price": 30.0, "stock_quantity": 5, "description": "Kan sulandırıcı"}
]

customers_db = []  # Müşteri listesi
sales_db = []      # Satış geçmişi

# --- MODELLER ---
class UserLogin(BaseModel):
    username: str
    password: str

class Drug(BaseModel):
    id: Optional[int] = None
    name: str
    active_ingredient: str
    price: float
    stock_quantity: int
    description: Optional[str] = None

class Customer(BaseModel):
    id: Optional[int] = None
    name: str
    tc_no: str
    phone: str

class SaleRequest(BaseModel):
    drug_id: int
    quantity: int
    customer_id: Optional[int] = None  # Müşterisiz de satılabilir

class OrderRequest(BaseModel): # Depo Siparişi için
    drug_id: int
    quantity: int

# --- ENDPOINTLER ---

@app.post("/login")
def login(user: UserLogin):
    db_user = users_db.get(user.username)
    if not db_user or db_user["password"] != user.password:
        raise HTTPException(status_code=401, detail="Hatalı kullanıcı adı veya şifre")
    
    return {
        "token": f"fake-jwt-token-{user.username}", 
        "user_info": {"username": user.username, "role": db_user["role"]}
    }

# --- İLAÇ YÖNETİMİ ---
@app.get("/drugs", response_model=List[Drug])
def get_drugs():
    return drugs_db

@app.post("/drugs", status_code=201)
def add_drug(drug: Drug):
    drug.id = len(drugs_db) + 1
    drugs_db.append(drug.dict())
    return drug

@app.delete("/drugs/{drug_id}")
def delete_drug(drug_id: int):
    global drugs_db
    drugs_db = [d for d in drugs_db if d["id"] != drug_id]
    return {"message": "İlaç silindi"}

# --- DEPO ENTEGRASYONU (SİPARİŞ) ---
@app.post("/order_stock")
def order_stock(order: OrderRequest):
    # Simülasyon: Ecza Deposu ile konuşuluyor...
    print(f"LOG: Depodan {order.quantity} adet ilaç sipariş edildi.")
    
    for drug in drugs_db:
        if drug["id"] == order.drug_id:
            drug["stock_quantity"] += order.quantity
            return {"message": f"Depo onayı alındı. Stok güncellendi. Yeni Stok: {drug['stock_quantity']}"}
    
    raise HTTPException(status_code=404, detail="İlaç bulunamadı")

# --- İTS VE SATIŞ ---
@app.post("/sales", status_code=201)
def sell_drug(sale: SaleRequest):
    # 1. İlacı Bul
    drug = next((d for d in drugs_db if d["id"] == sale.drug_id), None)
    if not drug:
        raise HTTPException(status_code=404, detail="İlaç bulunamadı")
    
    # 2. Stok Kontrolü
    if drug["stock_quantity"] < sale.quantity:
        raise HTTPException(status_code=400, detail="Yetersiz stok")

    # 3. İTS SİMÜLASYONU (Diyagramdaki ITS Adımı)
    its_transaction_id = random.randint(100000, 999999)
    print(f"LOG: İTS Sistemine bağlanıldı. Reçete/Satış onayı alındı. ID: {its_transaction_id}")

    # 4. Satışı Gerçekleştir
    drug["stock_quantity"] -= sale.quantity
    
    sale_record = {
        "id": len(sales_db) + 1,
        "drug_name": drug["name"],
        "quantity": sale.quantity,
        "total_price": drug["price"] * sale.quantity,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "customer_id": sale.customer_id,
        "its_id": its_transaction_id
    }
    sales_db.append(sale_record)

    return {"message": "Satış başarılı. İTS onayı alındı.", "sale": sale_record}

# --- MÜŞTERİ YÖNETİMİ ---
@app.get("/customers")
def get_customers():
    return customers_db

@app.post("/customers")
def add_customer(customer: Customer):
    customer.id = len(customers_db) + 1
    customers_db.append(customer.dict())
    return customer

@app.get("/customers/{customer_id}/history")
def get_customer_history(customer_id: int):
    # Müşterinin geçmiş siparişlerini bul
    history = [s for s in sales_db if s["customer_id"] == customer_id]
    return history

# --- RAPORLAMA ---
@app.get("/reports/daily")
def get_daily_report():
    total_sales = len(sales_db)
    total_revenue = sum(s["total_price"] for s in sales_db)
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_sales_count": total_sales,
        "total_revenue": total_revenue,
        "details": sales_db
    }