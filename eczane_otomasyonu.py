from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import random
import threading
import time

app = FastAPI()

# Alert servisini import et
try:
    from alerts.alert_service import alert_service
    ALERTS_ENABLED = True
except ImportError:
    ALERTS_ENABLED = False
    print("Uyarı servisi devre dışı")

# --- VERİTABANI (Güncellendi) ---
users_db = {
    "yonetici": {"password": "admin123", "role": "Yönetici"},
    "personel": {"password": "123", "role": "Personel"}
}

# İlaçlara low_stock_threshold eklendi
drugs_db = [
    {"id": 1, "name": "Parol", "active_ingredient": "Parasetamol", "price": 50.0, 
     "stock_quantity": 100, "description": "Ağrı kesici", "low_stock_threshold": 10},
    {"id": 2, "name": "Majezik", "active_ingredient": "Flurbiprofen", "price": 85.0, 
     "stock_quantity": 20, "description": "Anti-enflamatuar", "low_stock_threshold": 5},
    {"id": 3, "name": "Aspirin", "active_ingredient": "Asetilsalisilik Asit", "price": 30.0, 
     "stock_quantity": 5, "description": "Kan sulandırıcı", "low_stock_threshold": 10},
    {"id": 4, "name": "Augmentin", "active_ingredient": "Amoksisilin", "price": 120.0, 
     "stock_quantity": 3, "description": "Antibiyotik", "low_stock_threshold": 5},
    {"id": 5, "name": "Ventolin", "active_ingredient": "Salbutamol", "price": 45.0, 
     "stock_quantity": 15, "description": "Astım ilacı", "low_stock_threshold": 8}
]

customers_db = []
sales_db = []
alert_history = []  # Uyarı geçmişi

# --- YENİ MODELLER ---
class DrugCreate(BaseModel):
    name: str
    active_ingredient: str
    price: float
    stock_quantity: int
    description: Optional[str] = None
    low_stock_threshold: Optional[int] = 10  # Yeni alan

class AlertSettings(BaseModel):
    enable_email: bool = True
    enable_sms: bool = False
    enable_auto_order: bool = False
    check_interval_minutes: int = 60
    low_stock_threshold: int = 10
    critical_stock_threshold: int = 5
    auto_order_quantity: int = 50

# --- MEVCUT MODELLER (güncellendi) ---
class Drug(BaseModel):
    id: Optional[int] = None
    name: str
    active_ingredient: str
    price: float
    stock_quantity: int
    description: Optional[str] = None
    low_stock_threshold: Optional[int] = 10  # Yeni alan eklendi

# --- YENİ ENDPOINTLER ---

@app.on_event("startup")
def startup_event():
    """Uygulama başlarken alert servisini başlat"""
    if ALERTS_ENABLED:
        alert_service.start_scheduler()
        print("🔄 Otomatik stok uyarı servisi aktif")

@app.get("/alerts/check")
def manual_stock_check():
    """Manuel stok kontrolü"""
    if ALERTS_ENABLED:
        alert_service.check_stock_levels()
        return {"message": "Stok kontrolü manuel başlatıldı"}
    return {"message": "Alert servisi devre dışı"}

@app.get("/alerts/history")
def get_alert_history():
    """Uyarı geçmişini getir"""
    if ALERTS_ENABLED:
        return alert_service.get_alert_history()
    return []

@app.get("/drugs/low-stock")
def get_low_stock_drugs():
    """Düşük stoklu ilaçları listele"""
    low_stock = []
    for drug in drugs_db:
        if drug["stock_quantity"] <= drug.get("low_stock_threshold", 10):
            low_stock.append(drug)
    return low_stock

@app.get("/drugs/critical-stock")
def get_critical_stock_drugs():
    """Kritik stoklu ilaçları listele"""
    critical_stock = []
    for drug in drugs_db:
        if drug["stock_quantity"] <= 5:  # Kritik eşik
            critical_stock.append(drug)
    return critical_stock

@app.put("/drugs/{drug_id}/threshold")
def update_stock_threshold(drug_id: int, threshold: int):
    """İlaç için stok uyarı eşiğini güncelle"""
    for drug in drugs_db:
        if drug["id"] == drug_id:
            drug["low_stock_threshold"] = threshold
            
            # Hemen kontrol et
            if ALERTS_ENABLED and drug["stock_quantity"] <= threshold:
                alert_service.handle_low_stock([drug])
            
            return {"message": f"{drug['name']} için stok eşiği {threshold} olarak güncellendi"}
    
    raise HTTPException(404, "İlaç bulunamadı")

@app.get("/alerts/settings")
def get_alert_settings():
    """Mevcut uyarı ayarlarını getir"""
    return {
        "enable_email": True,
        "enable_sms": False,
        "enable_auto_order": False,
        "check_interval_minutes": 60,
        "default_low_threshold": 10,
        "default_critical_threshold": 5
    }

# --- MEVCUT ENDPOINT GÜNCELLEMELERİ ---

@app.post("/drugs", status_code=201)
def add_drug(drug: DrugCreate):
    """Yeni ilaç ekle (low_stock_threshold desteği ile)"""
    new_id = len(drugs_db) + 1
    drug_dict = drug.dict()
    drug_dict["id"] = new_id
    drugs_db.append(drug_dict)
    
    # Yeni eklenen ilaç stok kontrolü
    if ALERTS_ENABLED and drug.stock_quantity <= drug.low_stock_threshold:
        alert_service.handle_low_stock([drug_dict])
    
    return drug_dict

@app.post("/sales", status_code=201)
def sell_drug(sale: SaleRequest):
    """Satış yap (stok azaldıktan sonra kontrol et)"""
    drug = next((d for d in drugs_db if d["id"] == sale.drug_id), None)
    if not drug:
        raise HTTPException(404, "İlaç bulunamadı")
    
    if drug["stock_quantity"] < sale.quantity:
        raise HTTPException(400, "Yetersiz stok")
    
    # Satışı gerçekleştir
    drug["stock_quantity"] -= sale.quantity
    
    its_transaction_id = random.randint(100000, 999999)
    
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
    
    # Satış sonrası stok kontrolü
    if ALERTS_ENABLED:
        # Hemen kontrol et (arka planda)
        def check_after_sale():
            time.sleep(2)  # 2 saniye bekle
            if drug["stock_quantity"] <= drug.get("low_stock_threshold", 10):
                alert_service.check_stock_levels()
        
        # Arka plan görevi başlat
        import threading
        thread = threading.Thread(target=check_after_sale)
        thread.start()
    
    return {"message": "Satış başarılı. İTS onayı alındı.", "sale": sale_record}

@app.post("/order_stock")
def order_stock(order: OrderRequest):
    """Depodan stok siparişi (otomatik sipariş desteği)"""
    for drug in drugs_db:
        if drug["id"] == order.drug_id:
            old_stock = drug["stock_quantity"]
            drug["stock_quantity"] += order.quantity
            
            # Otomatik sipariş logu
            auto_order = getattr(order, 'auto_order', False)
            urgent = getattr(order, 'urgent', False)
            
            log_msg = f"Depodan {order.quantity} adet ilaç sipariş edildi."
            if auto_order:
                log_msg = f"OTOMATİK SİPARİŞ: {log_msg}"
            if urgent:
                log_msg = f"ACİL {log_msg}"
            
            print(f"LOG: {log_msg} İlaç: {drug['name']}, Eski: {old_stock}, Yeni: {drug['stock_quantity']}")
            
            return {
                "message": log_msg,
                "old_stock": old_stock,
                "new_stock": drug["stock_quantity"],
                "auto_order": auto_order,
                "urgent": urgent
            }
    
    raise HTTPException(404, "İlaç bulunamadı")

# --- YENİ RAPORLAMA ENDPOINTLERİ ---

@app.get("/reports/stock-status")
def get_stock_status_report():
    """Stok durum raporu"""
    total_drugs = len(drugs_db)
    total_stock_value = sum(d["stock_quantity"] * d["price"] for d in drugs_db)
    low_stock_count = len([d for d in drugs_db if d["stock_quantity"] <= d.get("low_stock_threshold", 10)])
    critical_stock_count = len([d for d in drugs_db if d["stock_quantity"] <= 5])
    
    return {
        "total_drugs": total_drugs,
        "total_stock_value": total_stock_value,
        "low_stock_count": low_stock_count,
        "critical_stock_count": critical_stock_count,
        "check_time": datetime.now().isoformat()
    }

# --- MEVCUT ENDPOINTLER (değişmedi) ---
# [Login, customers, daily reports vb. mevcut kodlar aynı kalacak]
# ...

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)