# eczane_otomasyonu.py - PostgreSQL ile Tam Entegre
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import random
import time
import hashlib
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

# Database modüllerini import et
from database import get_db, SessionLocal, init_database
from database import User, Drug, Customer, Sale, StockMovement, Alert

app = FastAPI(title="Eczane Otomasyonu API", version="3.0 - PostgreSQL")

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Alert servisini import et
try:
    from alerts.alert_service import alert_service
    ALERTS_ENABLED = True
except ImportError:
    ALERTS_ENABLED = False
    print("Uyarı servisi devre dışı")

# ================ PYDANTIC MODELLER ================

class LoginRequest(BaseModel):
    username: str
    password: str

class DrugCreate(BaseModel):
    name: str
    active_ingredient: str
    price: float
    stock_quantity: int
    description: Optional[str] = None
    low_stock_threshold: Optional[int] = 10

class SaleRequest(BaseModel):
    drug_id: int
    quantity: int = 1
    customer_id: Optional[int] = None

class OrderRequest(BaseModel):
    drug_id: int
    quantity: int = 10
    auto_order: bool = False

class CustomerCreate(BaseModel):
    name: str
    tc_no: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None

class DrugResponse(BaseModel):
    id: int
    name: str
    active_ingredient: str
    price: float
    stock_quantity: int
    low_stock_threshold: int
    description: Optional[str] = None

# ================ YARDIMCI FONKSİYONLAR ================

def hash_password(password: str) -> str:
    """Basit şifre hashleme"""
    return hashlib.md5(password.encode()).hexdigest()

def create_token(username: str) -> str:
    """Basit token oluştur"""
    return hashlib.md5(f"{username}{time.time()}".encode()).hexdigest()

def check_stock_levels(db: Session):
    """Stok seviyelerini kontrol et ve uyarı oluştur"""
    try:
        drugs = db.query(Drug).all()
        for drug in drugs:
            if drug.stock_quantity <= 5:
                # Kritik stok uyarısı
                alert = Alert(
                    drug_id=drug.id,
                    alert_type="critical_stock",
                    message=f"{drug.name} kritik stokta! ({drug.stock_quantity} adet kaldı)"
                )
                db.add(alert)
            elif drug.stock_quantity <= drug.low_stock_threshold:
                # Düşük stok uyarısı
                alert = Alert(
                    drug_id=drug.id,
                    alert_type="low_stock",
                    message=f"{drug.name} düşük stokta. Eşik: {drug.low_stock_threshold}, Mevcut: {drug.stock_quantity}"
                )
                db.add(alert)
        db.commit()
    except Exception as e:
        print(f"Stok kontrol hatası: {e}")

def log_stock_movement(db: Session, drug_id: int, movement_type: str, 
                       quantity_change: int, previous_qty: int, reason: str = ""):
    """Stok hareketini logla"""
    try:
        movement = StockMovement(
            drug_id=drug_id,
            movement_type=movement_type,
            quantity_change=quantity_change,
            previous_quantity=previous_qty,
            new_quantity=previous_qty + quantity_change,
            reason=reason,
            created_by=1  # Default admin user
        )
        db.add(movement)
        db.commit()
    except Exception as e:
        print(f"Stok log hatası: {e}")

# ================ UYGULAMA BAŞLANGICI ================

@app.on_event("startup")
def startup_event():
    """Uygulama başlarken veritabanını başlat"""
    try:
        init_database()
        print("✅ PostgreSQL veritabanı hazır")
        
        # Demo kullanıcıları kontrol et
        db = SessionLocal()
        if db.query(User).count() == 0:
            # Demo kullanıcıları ekle
            admin = User(
                username="yonetici",
                password_hash=hash_password("admin123"),
                role="Yönetici",
                full_name="Eczane Yöneticisi"
            )
            personel = User(
                username="personel", 
                password_hash=hash_password("123"),
                role="Personel",
                full_name="Eczane Personeli"
            )
            db.add(admin)
            db.add(personel)
            db.commit()
            print("✅ Demo kullanıcılar eklendi")
        
        if db.query(Drug).count() == 0:
            # Demo ilaçları ekle
            demo_drugs = [
                Drug(name="Parol", active_ingredient="Parasetamol", price=50.0, 
                     stock_quantity=100, low_stock_threshold=10, description="Ağrı kesici"),
                Drug(name="Majezik", active_ingredient="Flurbiprofen", price=85.0, 
                     stock_quantity=20, low_stock_threshold=5, description="Anti-enflamatuar"),
                Drug(name="Aspirin", active_ingredient="Asetilsalisilik Asit", price=30.0, 
                     stock_quantity=5, low_stock_threshold=10, description="Kan sulandırıcı"),
                Drug(name="Augmentin", active_ingredient="Amoksisilin", price=120.0, 
                     stock_quantity=3, low_stock_threshold=5, description="Antibiyotik"),
                Drug(name="Ventolin", active_ingredient="Salbutamol", price=45.0, 
                     stock_quantity=15, low_stock_threshold=8, description="Astım ilacı")
            ]
            for drug in demo_drugs:
                db.add(drug)
            db.commit()
            print("✅ Demo ilaçlar eklendi")
        
        db.close()
        
        if ALERTS_ENABLED:
            alert_service.start_scheduler()
            print("🔄 Otomatik stok uyarı servisi aktif")
            
    except Exception as e:
        print(f"❌ Startup hatası: {e}")

# ================ AUTH ENDPOINT'LERİ ================

@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Kullanıcı girişi"""
    user = db.query(User).filter(User.username == request.username).first()
    
    if not user or user.password_hash != hash_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı"
        )
    
    token = create_token(request.username)
    
    return {
        "token": token,
        "role": user.role,
        "user_info": {
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name
        }
    }

# ================ İLAÇ ENDPOINT'LERİ ================

@app.get("/drugs")
def get_all_drugs(db: Session = Depends(get_db)):
    """Tüm ilaçları getir"""
    drugs = db.query(Drug).order_by(Drug.name).all()
    return [{
        "id": d.id,
        "name": d.name,
        "active_ingredient": d.active_ingredient,
        "price": float(d.price),
        "stock_quantity": d.stock_quantity,
        "low_stock_threshold": d.low_stock_threshold,
        "description": d.description
    } for d in drugs]

@app.get("/drugs/{drug_id}")
def get_drug(drug_id: int, db: Session = Depends(get_db)):
    """Belirli bir ilacı getir"""
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(404, "İlaç bulunamadı")
    return drug

@app.post("/drugs", status_code=201)
def add_drug(drug: DrugCreate, db: Session = Depends(get_db)):
    """Yeni ilaç ekle"""
    # Aynı isimde ilaç var mı kontrol et
    existing = db.query(Drug).filter(Drug.name == drug.name).first()
    if existing:
        raise HTTPException(400, "Bu isimde ilaç zaten var")
    
    new_drug = Drug(
        name=drug.name,
        active_ingredient=drug.active_ingredient,
        price=drug.price,
        stock_quantity=drug.stock_quantity,
        low_stock_threshold=drug.low_stock_threshold,
        description=drug.description
    )
    
    db.add(new_drug)
    db.commit()
    db.refresh(new_drug)
    
    # Stok logu
    log_stock_movement(db, new_drug.id, "purchase", drug.stock_quantity, 0, "İlk stok ekleme")
    
    # Stok kontrolü
    check_stock_levels(db)
    
    return {
        "id": new_drug.id,
        "name": new_drug.name,
        "message": "İlaç başarıyla eklendi"
    }

@app.put("/drugs/{drug_id}/threshold")
def update_stock_threshold(drug_id: int, threshold: int, db: Session = Depends(get_db)):
    """Stok uyarı eşiğini güncelle"""
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(404, "İlaç bulunamadı")
    
    old_threshold = drug.low_stock_threshold
    drug.low_stock_threshold = threshold
    drug.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Eşik düşürüldüyse ve stok yetersizse uyarı oluştur
    if threshold < old_threshold and drug.stock_quantity <= threshold:
        check_stock_levels(db)
    
    return {
        "message": f"{drug.name} için stok eşiği {threshold} olarak güncellendi",
        "drug": {
            "id": drug.id,
            "name": drug.name,
            "stock_quantity": drug.stock_quantity,
            "low_stock_threshold": drug.low_stock_threshold
        }
    }

@app.delete("/drugs/{drug_id}")
def delete_drug(drug_id: int, db: Session = Depends(get_db)):
    """İlaç sil"""
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(404, "İlaç bulunamadı")
    
    db.delete(drug)
    db.commit()
    
    return {"message": f"{drug.name} başarıyla silindi"}

# ================ SATIŞ ENDPOINT'LERİ ================

@app.post("/sales", status_code=201)
def sell_drug(sale: SaleRequest, db: Session = Depends(get_db)):
    """Satış yap"""
    # İlacı bul
    drug = db.query(Drug).filter(Drug.id == sale.drug_id).first()
    if not drug:
        raise HTTPException(404, "İlaç bulunamadı")
    
    # Stok kontrolü
    if drug.stock_quantity < sale.quantity:
        raise HTTPException(400, f"Yetersiz stok. Mevcut: {drug.stock_quantity}")
    
    # Müşteriyi bul (varsa)
    customer = None
    if sale.customer_id:
        customer = db.query(Customer).filter(Customer.id == sale.customer_id).first()
    
    # Önceki stok miktarını kaydet
    previous_stock = drug.stock_quantity
    
    # Stok güncelle
    drug.stock_quantity -= sale.quantity
    drug.updated_at = datetime.utcnow()
    
    # Satış kaydı oluştur
    its_id = random.randint(100000, 999999)
    new_sale = Sale(
        drug_id=drug.id,
        customer_id=customer.id if customer else None,
        quantity=sale.quantity,
        unit_price=float(drug.price),
        total_price=float(drug.price * sale.quantity),
        its_transaction_id=str(its_id),
        created_by=1  # Default user
    )
    
    # Stok hareketi logu
    log_stock_movement(db, drug.id, "sale", -sale.quantity, previous_stock, 
                      f"{sale.quantity} adet satış")
    
    db.add(new_sale)
    db.commit()
    
    # Stok kontrolü (arka planda)
    def check_after_sale():
        time.sleep(1)
        check_stock_levels(db)
    
    import threading
    threading.Thread(target=check_after_sale).start()
    
    return {
        "message": "Satış başarılı. İTS onayı alındı.",
        "sale": {
            "id": new_sale.id,
            "drug_name": drug.name,
            "quantity": sale.quantity,
            "total_price": float(new_sale.total_price),
            "its_id": its_id,
            "date": new_sale.sale_date.isoformat()
        }
    }

# ================ MÜŞTERİ ENDPOINT'LERİ ================

@app.get("/customers")
def get_customers(db: Session = Depends(get_db)):
    """Tüm müşterileri getir"""
    customers = db.query(Customer).order_by(Customer.name).all()
    return [{
        "id": c.id,
        "name": c.name,
        "tc_no": c.tc_no,
        "phone": c.phone,
        "email": c.email,
        "created_at": c.created_at.isoformat() if c.created_at else None
    } for c in customers]

@app.post("/customers", status_code=201)
def add_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
    """Yeni müşteri ekle"""
    # TC kontrolü
    if customer.tc_no:
        existing = db.query(Customer).filter(Customer.tc_no == customer.tc_no).first()
        if existing:
            raise HTTPException(400, "Bu TC numarası zaten kayıtlı")
    
    new_customer = Customer(
        name=customer.name,
        tc_no=customer.tc_no,
        phone=customer.phone,
        email=customer.email
    )
    
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    
    return {
        "id": new_customer.id,
        "name": new_customer.name,
        "message": "Müşteri başarıyla eklendi"
    }

@app.get("/customers/{customer_id}/history")
def get_customer_history(customer_id: int, db: Session = Depends(get_db)):
    """Müşteri satış geçmişi"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Müşteri bulunamadı")
    
    sales = db.query(Sale).filter(Sale.customer_id == customer_id)\
              .join(Drug).order_by(desc(Sale.sale_date)).all()
    
    return [{
        "id": s.id,
        "drug_name": s.drug.name if s.drug else "Silinmiş İlaç",
        "quantity": s.quantity,
        "total_price": float(s.total_price),
        "date": s.sale_date.strftime("%Y-%m-%d %H:%M"),
        "its_id": s.its_transaction_id
    } for s in sales]

# ================ STOK SİPARİŞİ ================

@app.post("/order_stock")
def order_stock(order: OrderRequest, db: Session = Depends(get_db)):
    """Depodan stok siparişi"""
    drug = db.query(Drug).filter(Drug.id == order.drug_id).first()
    if not drug:
        raise HTTPException(404, "İlaç bulunamadı")
    
    previous_stock = drug.stock_quantity
    drug.stock_quantity += order.quantity
    drug.updated_at = datetime.utcnow()
    
    # Stok logu
    log_movement_type = "auto_purchase" if order.auto_order else "purchase"
    log_stock_movement(db, drug.id, log_movement_type, order.quantity, 
                      previous_stock, f"Depo siparişi: {order.quantity} adet")
    
    db.commit()
    
    message = f"{order.quantity} adet {drug.name} sipariş edildi"
    if order.auto_order:
        message = f"OTOMATİK SİPARİŞ: {message}"
    
    return {
        "message": message,
        "old_stock": previous_stock,
        "new_stock": drug.stock_quantity,
        "auto_order": order.auto_order
    }

# ================ RAPORLAMA ENDPOINT'LERİ ================

@app.get("/reports/daily")
def get_daily_report(db: Session = Depends(get_db)):
    """Günlük rapor"""
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    
    # Bugünkü satışlar
    today_sales = db.query(Sale).filter(
        Sale.sale_date >= today,
        Sale.sale_date < tomorrow
    ).all()
    
    # Toplam satış miktarı ve cirosu
    total_count = len(today_sales)
    total_revenue = sum(float(s.total_price) for s in today_sales)
    
    # Satış detayları
    details = []
    for sale in today_sales:
        drug = db.query(Drug).filter(Drug.id == sale.drug_id).first()
        details.append({
            "drug_name": drug.name if drug else "Silinmiş İlaç",
            "quantity": sale.quantity,
            "total_price": float(sale.total_price),
            "its_id": sale.its_transaction_id,
            "date": sale.sale_date.strftime("%Y-%m-%d %H:%M")
        })
    
    return {
        "date": today.strftime("%Y-%m-%d"),
        "total_sales_count": total_count,
        "total_revenue": total_revenue,
        "details": details
    }

@app.get("/reports/stock-status")
def get_stock_status_report(db: Session = Depends(get_db)):
    """Stok durum raporu"""
    # Toplam ilaç sayısı
    total_drugs = db.query(Drug).count()
    
    # Toplam stok değeri
    total_stock_value = db.query(func.sum(Drug.price * Drug.stock_quantity)).scalar() or 0
    
    # Düşük ve kritik stok sayıları
    low_stock = db.query(Drug).filter(Drug.stock_quantity <= Drug.low_stock_threshold).count()
    critical_stock = db.query(Drug).filter(Drug.stock_quantity <= 5).count()
    
    # En düşük stoklu ilaç
    min_stock_drug = db.query(Drug).order_by(Drug.stock_quantity).first()
    
    return {
        "total_drugs": total_drugs,
        "total_stock_value": float(total_stock_value),
        "low_stock_count": low_stock,
        "critical_stock_count": critical_stock,
        "min_stock_drug": {
            "name": min_stock_drug.name if min_stock_drug else "Yok",
            "stock": min_stock_drug.stock_quantity if min_stock_drug else 0
        },
        "check_time": datetime.utcnow().isoformat()
    }

# ================ UYARI ENDPOINT'LERİ ================

@app.get("/alerts/check")
def manual_stock_check(db: Session = Depends(get_db)):
    """Manuel stok kontrolü"""
    check_stock_levels(db)
    return {"message": "Stok kontrolü tamamlandı"}

@app.get("/alerts/history")
def get_alert_history(db: Session = Depends(get_db)):
    """Uyarı geçmişi"""
    alerts = db.query(Alert).join(Drug).order_by(desc(Alert.created_at)).limit(50).all()
    
    return [{
        "id": a.id,
        "drug_name": a.drug.name if a.drug else "Silinmiş İlaç",
        "alert_type": a.alert_type,
        "message": a.message,
        "is_read": a.is_read,
        "created_at": a.created_at.isoformat() if a.created_at else None
    } for a in alerts]

@app.get("/drugs/low-stock")
def get_low_stock_drugs(db: Session = Depends(get_db)):
    """Düşük stoklu ilaçlar"""
    drugs = db.query(Drug).filter(Drug.stock_quantity <= Drug.low_stock_threshold).all()
    
    return [{
        "id": d.id,
        "name": d.name,
        "stock_quantity": d.stock_quantity,
        "low_stock_threshold": d.low_stock_threshold,
        "price": float(d.price)
    } for d in drugs]

@app.get("/drugs/critical-stock")
def get_critical_stock_drugs(db: Session = Depends(get_db)):
    """Kritik stoklu ilaçlar"""
    drugs = db.query(Drug).filter(Drug.stock_quantity <= 5).all()
    
    return [{
        "id": d.id,
        "name": d.name,
        "stock_quantity": d.stock_quantity,
        "low_stock_threshold": d.low_stock_threshold,
        "price": float(d.price)
    } for d in drugs]

# ================ ROOT ENDPOINT ================

@app.get("/")
def root():
    return {
        "message": "🏥 Eczane Otomasyonu Backend API v3.0",
        "status": "active",
        "database": "PostgreSQL",
        "endpoints": {
            "auth": "/login (POST)",
            "drugs": "/drugs (GET, POST, PUT, DELETE)",
            "sales": "/sales (POST)",
            "customers": "/customers (GET, POST)",
            "reports": "/reports/daily, /reports/stock-status",
            "alerts": "/alerts/check, /alerts/history",
            "docs": "/docs (Swagger UI)"
        }
    }

# ================ UYGULAMA ÇALIŞTIRMA ================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)