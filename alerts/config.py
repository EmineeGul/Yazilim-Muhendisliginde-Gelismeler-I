# alerts/config.py
"""
E-posta ve SMS ayarları için konfigürasyon dosyası
.env dosyasına ihtiyaç duymadan çalışır
"""

import os

# ==================== E-POSTA AYARLARI (DEMO MOD) ====================
EMAIL_CONFIG = {
    "SMTP_SERVER": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    "SMTP_PORT": int(os.environ.get("SMTP_PORT", 587)),
    "EMAIL_ADDRESS": os.environ.get("ALERT_EMAIL", "demo@eczane.com"),
    "EMAIL_PASSWORD": os.environ.get("EMAIL_PASSWORD", ""),
    "ADMIN_EMAILS": [
        os.environ.get("ADMIN_EMAIL_1", "yonetici@eczane.com"),
        os.environ.get("ADMIN_EMAIL_2", "depo@eczane.com")
    ],
    "ENABLE_EMAIL_ALERTS": os.environ.get("ENABLE_EMAIL_ALERTS", "false").lower() == "true"
}

# ==================== SMS AYARLARI (DEMO MOD) ====================
SMS_CONFIG = {
    "SMS_API_KEY": os.environ.get("SMS_API_KEY", ""),
    "SMS_API_URL": os.environ.get("SMS_API_URL", "https://api.netgsm.com.tr/sms/send/get"),
    "ADMIN_PHONES": [
        os.environ.get("ADMIN_PHONE_1", "+905551112233"),
        os.environ.get("ADMIN_PHONE_2", "+905554445566")
    ],
    "ENABLE_SMS_ALERTS": os.environ.get("ENABLE_SMS_ALERTS", "false").lower() == "true"
}

# ==================== UYARI AYARLARI ====================
ALERT_CONFIG = {
    "CHECK_INTERVAL_MINUTES": int(os.environ.get("CHECK_INTERVAL", 60)),
    "LOW_STOCK_THRESHOLD": int(os.environ.get("LOW_STOCK_THRESHOLD", 10)),
    "CRITICAL_STOCK_THRESHOLD": int(os.environ.get("CRITICAL_STOCK_THRESHOLD", 5)),
    "AUTO_ORDER_QUANTITY": int(os.environ.get("AUTO_ORDER_QUANTITY", 50)),
    "ENABLE_AUTO_ORDER": os.environ.get("ENABLE_AUTO_ORDER", "false").lower() == "true"
}

# ==================== DEMO MOD AYARLARI ====================
# Eğer .env yoksa demo modda çalış
DEMO_MODE = not os.path.exists(".env") and not os.environ.get("SMTP_SERVER")

if DEMO_MODE:
    print("🚨 DEMO MOD: .env dosyası bulunamadı, demo ayarları kullanılıyor")
    print("ℹ️  Gerçek e-posta/SMS gönderilmeyecek, sadece konsola log yazılacak")
    
    # Demo ayarları
    EMAIL_CONFIG.update({
        "ENABLE_EMAIL_ALERTS": False,
        "EMAIL_ADDRESS": "demo@eczane.com"
    })
    
    SMS_CONFIG.update({
        "ENABLE_SMS_ALERTS": False
    })
    
    ALERT_CONFIG.update({
        "CHECK_INTERVAL_MINUTES": 5,  # Demo'da 5 dakikada bir kontrol
        "ENABLE_AUTO_ORDER": False
    })