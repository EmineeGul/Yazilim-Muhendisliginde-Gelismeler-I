# alerts/alert_service.py
"""
Otomatik stok uyarı ve bildirim servisi
Demo mod: E-posta/SMS göndermez, sadece konsola yazar
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import json
from datetime import datetime
import schedule
import time
import threading
from .config import EMAIL_CONFIG, SMS_CONFIG, ALERT_CONFIG, DEMO_MODE

class StockAlertService:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.alerts_sent = []  # Gönderilen uyarıların geçmişi
        
    def check_stock_levels(self):
        """Tüm ilaçların stok seviyelerini kontrol et"""
        print(f"[{datetime.now()}] Stok kontrolü başlatılıyor...")
        
        try:
            # API'den ilaçları çek
            response = requests.get(f"{self.api_url}/drugs")
            if response.status_code == 200:
                drugs = response.json()
                low_stock_drugs = []
                critical_stock_drugs = []
                
                for drug in drugs:
                    stock = drug.get("stock_quantity", 0)
                    threshold = drug.get("low_stock_threshold", ALERT_CONFIG["LOW_STOCK_THRESHOLD"])
                    
                    if stock <= ALERT_CONFIG["CRITICAL_STOCK_THRESHOLD"]:
                        critical_stock_drugs.append(drug)
                    elif stock <= threshold:
                        low_stock_drugs.append(drug)
                
                # Uyarıları işle
                if critical_stock_drugs:
                    self.handle_critical_stock(critical_stock_drugs)
                
                if low_stock_drugs:
                    self.handle_low_stock(low_stock_drugs)
                    
                print(f"[{datetime.now()}] Kontrol tamamlandı. "
                      f"Kritik: {len(critical_stock_drugs)}, Düşük: {len(low_stock_drugs)}")
                
                return {
                    "critical": critical_stock_drugs,
                    "low": low_stock_drugs
                }
                
        except Exception as e:
            print(f"Stok kontrolü hatası: {e}")
        
        return {"critical": [], "low": []}
    
    def handle_low_stock(self, drugs):
        """Düşük stok uyarısı"""
        alert_id = f"low_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Demo mod kontrolü
        if DEMO_MODE:
            print(f"🔶 DEMO: Düşük stok uyarısı (e-posta gönderilmez)")
            print(f"    İlaçlar: {[d['name'] for d in drugs]}")
        else:
            # E-posta gönder
            if EMAIL_CONFIG["ENABLE_EMAIL_ALERTS"]:
                self.send_email_alert(drugs, "DÜŞÜK STOK UYARISI", "low")
            
            # SMS gönder
            if SMS_CONFIG["ENABLE_SMS_ALERTS"]:
                self.send_sms_alert(drugs, "low")
        
        # Otomatik sipariş oluştur
        if ALERT_CONFIG["ENABLE_AUTO_ORDER"]:
            self.create_auto_orders(drugs)
        
        # Uyarı geçmişine kaydet
        self.record_alert(alert_id, drugs, "low")
    
    def handle_critical_stock(self, drugs):
        """Kritik stok uyarısı"""
        alert_id = f"critical_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Demo mod kontrolü
        if DEMO_MODE:
            print(f"🔴 DEMO: KRİTİK STOK UYARISI (e-posta gönderilmez)")
            print(f"    ACİL! İlaçlar: {[d['name'] for d in drugs]}")
        else:
            # Acil e-posta gönder
            if EMAIL_CONFIG["ENABLE_EMAIL_ALERTS"]:
                self.send_email_alert(drugs, "❗ KRİTİK STOK UYARISI ❗", "critical")
            
            # Acil SMS gönder
            if SMS_CONFIG["ENABLE_SMS_ALERTS"]:
                self.send_sms_alert(drugs, "critical")
        
        # Otomatik sipariş oluştur
        if ALERT_CONFIG["ENABLE_AUTO_ORDER"]:
            self.create_auto_orders(drugs, urgent=True)
        
        # Uyarı geçmişine kaydet
        self.record_alert(alert_id, drugs, "critical")
    
    def send_email_alert(self, drugs, subject, alert_type):
        """E-posta uyarısı gönder"""
        if DEMO_MODE:
            print(f"✉️  DEMO: E-posta gönderilecek (gerçekte gönderilmez)")
            print(f"    Konu: {subject}")
            print(f"    İlaçlar: {[d['name'] for d in drugs]}")
            return
        
        try:
            # E-posta içeriğini hazırla
            body = self.generate_email_body(drugs, alert_type)
            
            # E-posta oluştur
            msg = MIMEMultipart()
            msg['From'] = EMAIL_CONFIG["EMAIL_ADDRESS"]
            msg['To'] = ", ".join(EMAIL_CONFIG["ADMIN_EMAILS"])
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # SMTP sunucusuna bağlan ve gönder
            with smtplib.SMTP(EMAIL_CONFIG["SMTP_SERVER"], EMAIL_CONFIG["SMTP_PORT"]) as server:
                server.starttls()
                server.login(EMAIL_CONFIG["EMAIL_ADDRESS"], EMAIL_CONFIG["EMAIL_PASSWORD"])
                server.send_message(msg)
            
            print(f"✅ E-posta uyarısı gönderildi: {subject}")
            
        except Exception as e:
            print(f"❌ E-posta gönderme hatası: {e}")
    
    def send_sms_alert(self, drugs, alert_type):
        """SMS uyarısı gönder"""
        if DEMO_MODE:
            print(f"📱 DEMO: SMS gönderilecek (gerçekte gönderilmez)")
            print(f"    Tip: {alert_type}")
            print(f"    İlaçlar: {[d['name'] for d in drugs]}")
            return
        
        if not SMS_CONFIG["SMS_API_KEY"]:
            print("⚠️  SMS API anahtarı bulunamadı")
            return
        
        try:
            message = self.generate_sms_message(drugs, alert_type)
            
            # NetGSM API için örnek istek
            params = {
                "usercode": "demo_usercode",
                "password": SMS_CONFIG["SMS_API_KEY"],
                "gsmno": ",".join(SMS_CONFIG["ADMIN_PHONES"]),
                "message": message,
                "msgheader": "ECZANE_OTO"
            }
            
            response = requests.get(SMS_CONFIG["SMS_API_URL"], params=params)
            
            if response.status_code == 200:
                print(f"✅ SMS uyarısı gönderildi")
            else:
                print(f"❌ SMS gönderme hatası: {response.text}")
                
        except Exception as e:
            print(f"❌ SMS gönderme hatası: {e}")
    
    def create_auto_orders(self, drugs, urgent=False):
        """Otomatik depo siparişleri oluştur"""
        if DEMO_MODE:
            print(f"📦 DEMO: Otomatik sipariş oluşturulacak (gerçekte oluşturulmaz)")
            print(f"    İlaçlar: {[d['name'] for d in drugs]}")
            print(f"    Acil: {urgent}")
            return
        
        for drug in drugs:
            try:
                order_quantity = ALERT_CONFIG["AUTO_ORDER_QUANTITY"]
                if urgent:
                    order_quantity *= 2  # Acil durumda iki kat sipariş
                
                # API'ye sipariş isteği gönder
                payload = {
                    "drug_id": drug["id"],
                    "quantity": order_quantity,
                    "auto_order": True,
                    "urgent": urgent
                }
                
                response = requests.post(
                    f"{self.api_url}/order_stock",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    print(f"✅ Otomatik sipariş oluşturuldu: {drug['name']} x{order_quantity}")
                else:
                    print(f"❌ Sipariş oluşturulamadı: {response.status_code}")
                
            except Exception as e:
                print(f"❌ Sipariş oluşturma hatası {drug['name']}: {e}")
    
    def generate_email_body(self, drugs, alert_type):
        """E-posta içeriği oluştur"""
        if alert_type == "critical":
            header = "⛔ ACİL DURUM - KRİTİK STOK SEVİYESİ ⛔\n\n"
        else:
            header = "⚠️ DÜŞÜK STOK UYARISI ⚠️\n\n"
        
        body = header
        body += f"Tarih: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        body += "="*50 + "\n\n"
        
        for drug in drugs:
            body += f"• {drug['name']} ({drug['active_ingredient']})\n"
            body += f"  Mevcut Stok: {drug['stock_quantity']} adet\n"
            body += f"  Kritik Seviye: {drug.get('low_stock_threshold', 10)} adet\n"
            body += f"  Fiyat: {drug['price']} TL\n"
            body += "-"*30 + "\n"
        
        body += "\nLütfen stokları acilen yenileyiniz.\n\n"
        body += "Eczane Otomasyon Sistemi\n"
        body += "Otomatik Uyarı Sistemi"
        
        return body
    
    def generate_sms_message(self, drugs, alert_type):
        """SMS mesajı oluştur (max 160 karakter)"""
        if alert_type == "critical":
            message = "ACIL! "
        else:
            message = "UYARI! "
        
        drug_names = ", ".join([d["name"] for d in drugs[:3]])  # İlk 3 ilaç
        if len(drugs) > 3:
            drug_names += f" ve {len(drugs)-3} ilaç daha"
        
        message += f"Stok dusuk: {drug_names}"
        
        return message[:160]  # SMS karakter sınırı
    
    def record_alert(self, alert_id, drugs, alert_type):
        """Uyarıyı geçmişe kaydet"""
        alert_record = {
            "id": alert_id,
            "timestamp": datetime.now().isoformat(),
            "type": alert_type,
            "drug_count": len(drugs),
            "drugs": [{"id": d["id"], "name": d["name"], "stock": d["stock_quantity"]} for d in drugs]
        }
        
        self.alerts_sent.append(alert_record)
        
        # Son 100 uyarıyı sakla
        if len(self.alerts_sent) > 100:
            self.alerts_sent = self.alerts_sent[-100:]
        
        print(f"📝 Uyarı kaydedildi: {alert_type} - {len(drugs)} ilaç")
    
    def get_alert_history(self):
        """Uyarı geçmişini getir"""
        return self.alerts_sent
    
    def start_scheduler(self):
        """Zamanlanmış görevleri başlat"""
        # Her X dakikada bir kontrol et
        interval = ALERT_CONFIG["CHECK_INTERVAL_MINUTES"]
        schedule.every(interval).minutes.do(self.check_stock_levels)
        
        # Ayrı bir thread'de schedule'ı çalıştır
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(1)
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        mode = "DEMO" if DEMO_MODE else "PROD"
        print(f"🔄 Stok kontrol servisi başlatıldı ({mode} MOD)")
        print(f"   ⏰ Kontrol aralığı: {interval} dakika")
        print(f"   📧 E-posta: {'AKTİF' if EMAIL_CONFIG['ENABLE_EMAIL_ALERTS'] else 'PASİF'}")
        print(f"   📱 SMS: {'AKTİF' if SMS_CONFIG['ENABLE_SMS_ALERTS'] else 'PASİF'}")
        print(f"   📦 Otomatik sipariş: {'AKTİF' if ALERT_CONFIG['ENABLE_AUTO_ORDER'] else 'PASİF'}")

# Global servis instance'ı
alert_service = StockAlertService()