# database.py - PostgreSQL Bağlantı ve ORM Modelleri
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# ================ DATABASE BAĞLANTISI ================

# PostgreSQL bağlantı URL'si
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://eczane_user:eczane_pass@postgres:5432/eczane_db"
)

# SQLAlchemy engine oluştur
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# SessionLocal oluştur
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class (tüm tablolar bundan türeyecek)
Base = declarative_base()

# ================ TABLO MODELLERİ ================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="personel")
    full_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    sales = relationship("Sale", back_populates="created_by_user")
    stock_movements = relationship("StockMovement", back_populates="user")

class Drug(Base):
    __tablename__ = "drugs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    active_ingredient = Column(String(100))
    price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, default=10)
    description = Column(Text)
    barcode = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    sales = relationship("Sale", back_populates="drug")
    stock_movements = relationship("StockMovement", back_populates="drug")
    alerts = relationship("Alert", back_populates="drug")

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    tc_no = Column(String(11), unique=True, index=True)
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # İlişkiler
    sales = relationship("Sale", back_populates="customer")

class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.id", ondelete="SET NULL"))
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    its_transaction_id = Column(String(50))
    sale_date = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)
    
    # İlişkiler
    drug = relationship("Drug", back_populates="sales")
    customer = relationship("Customer", back_populates="sales")
    created_by_user = relationship("User", back_populates="sales", foreign_keys=[created_by])

class StockMovement(Base):
    __tablename__ = "stock_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"))
    movement_type = Column(String(20), nullable=False)  # 'purchase', 'sale', 'adjustment'
    quantity_change = Column(Integer, nullable=False)
    previous_quantity = Column(Integer, nullable=False)
    new_quantity = Column(Integer, nullable=False)
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # İlişkiler
    drug = relationship("Drug", back_populates="stock_movements")
    user = relationship("User", back_populates="stock_movements")

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"))
    alert_type = Column(String(20), nullable=False)  # 'low_stock', 'critical_stock'
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # İlişkiler
    drug = relationship("Drug", back_populates="alerts")

# ================ YARDIMCI FONKSİYONLAR ================

def get_db():
    """Dependency injection için database session sağlar"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Tabloları veritabanında oluşturur"""
    Base.metadata.create_all(bind=engine)
    print("✅ PostgreSQL tabloları oluşturuldu!")

def init_database():
    """Veritabanını başlat ve tabloları oluştur"""
    create_tables()
    
    # Test bağlantısı
    db = SessionLocal()
    try:
        result = db.execute("SELECT version();")
        version = result.fetchone()[0]
        print(f"✅ PostgreSQL bağlantısı başarılı: {version}")
        
        # Tablo sayılarını kontrol et
        table_count = db.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';").fetchone()[0]
        print(f"✅ {table_count} tablo oluşturuldu")
        
    except Exception as e:
        print(f"❌ Database bağlantı hatası: {e}")
    finally:
        db.close()

# Uygulama başladığında tabloları oluştur
if __name__ == "__main__":
    init_database()