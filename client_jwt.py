"""
JWT Token Kullanan İstemci Uygulaması
Çalıştırma: python client_jwt.py
"""

import requests
import json
from datetime import datetime
import time

# API URL'leri
BASE_URL = "http://localhost:8001"
LOGIN_URL = f"{BASE_URL}/login"
PROFILE_URL = f"{BASE_URL}/profile"
VALIDATE_URL = f"{BASE_URL}/validate"
PROTECTED_URL = f"{BASE_URL}/protected"
USERS_URL = f"{BASE_URL}/users"

class JWTClient:
    def __init__(self):
        self.token = None
        self.user_info = None
        self.headers = {}
    
    def login(self, username, password):
        """Kullanıcı girişi yap ve token al"""
        try:
            response = requests.post(LOGIN_URL, json={
                "username": username,
                "password": password
            })
            
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.user_info = data["user_info"]
                self.headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
                print("✅ Giriş başarılı!")
                print(f"   Kullanıcı: {self.user_info['full_name']}")
                print(f"   Rol: {self.user_info['role']}")
                print(f"   Token: {self.token[:50]}...")
                return True
            else:
                print(f"❌ Giriş başarısız: {response.json().get('detail', 'Bilinmeyen hata')}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("❌ Sunucuya bağlanılamadı. server_jwt.py çalışıyor mu?")
            print(f"   Komut: uvicorn server_jwt:app --reload --port 8001")
            return False
    
    def get_profile(self):
        """Token ile profil bilgilerini getir"""
        if not self.token:
            print("❌ Önce giriş yapmalısınız!")
            return
        
        try:
            response = requests.get(PROFILE_URL, headers=self.headers)
            
            if response.status_code == 200:
                profile = response.json()
                print("\n📋 PROFİL BİLGİLERİ:")
                print(f"   Kullanıcı Adı: {profile['username']}")
                print(f"   Ad Soyad: {profile['full_name']}")
                print(f"   Rol: {profile['role']}")
                return profile
            else:
                print(f"❌ Profil alınamadı: {response.json().get('detail')}")
                
        except Exception as e:
            print(f"❌ Hata: {e}")
    
    def validate_token(self, token=None):
        """Token'ı doğrula"""
        token_to_validate = token or self.token
        
        if not token_to_validate:
            print("❌ Token gerekli!")
            return
        
        try:
            response = requests.post(VALIDATE_URL, json={
                "token": token_to_validate
            })
            
            result = response.json()
            print("\n🔐 TOKEN DOĞRULAMA:")
            print(f"   Geçerli mi: {'✅' if result['valid'] else '❌'}")
            print(f"   Kullanıcı: {result.get('username', 'N/A')}")
            print(f"   Rol: {result.get('role', 'N/A')}")
            print(f"   Mesaj: {result.get('message', 'N/A')}")
            return result
            
        except Exception as e:
            print(f"❌ Doğrulama hatası: {e}")
    
    def access_protected_endpoint(self):
        """Korumalı endpoint'e eriş"""
        if not self.token:
            print("❌ Önce giriş yapmalısınız!")
            return
        
        try:
            response = requests.get(PROTECTED_URL, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                print("\n🔒 KORUMALI ENDPOINT:")
                print(f"   Mesaj: {data['message']}")
                print(f"   Kullanıcı: {data['user_data']['username']}")
                print(f"   Token Süresi: {data['user_data']['token_expires']}")
                return data
            else:
                print(f"❌ Erişim reddedildi: {response.json().get('detail')}")
                
        except Exception as e:
            print(f"❌ Hata: {e}")
    
    def list_users(self):
        """Tüm kullanıcıları listele (sadece yönetici)"""
        if not self.token:
            print("❌ Önce giriş yapmalısınız!")
            return
        
        try:
            response = requests.get(USERS_URL, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n👥 TOPLAM {data['count']} KULLANICI:")
                for user in data['users']:
                    print(f"   👤 {user['full_name']} ({user['username']}) - {user['role']}")
                return data
            else:
                print(f"❌ Kullanıcılar listelenemedi: {response.json().get('detail')}")
                
        except Exception as e:
            print(f"❌ Hata: {e}")
    
    def decode_token_parts(self):
        """Token'ı manuel olarak decode et (eğitim amaçlı)"""
        if not self.token:
            print("❌ Önce giriş yapmalısınız!")
            return
        
        # Token'ı noktalara göre ayır
        parts = self.token.split('.')
        if len(parts) != 3:
            print("❌ Geçersiz JWT formatı")
            return
        
        print("\n🔍 TOKEN YAPISI:")
        print(f"   Header: {parts[0]}")
        print(f"   Payload: {parts[1]}")
        print(f"   Signature: {parts[2][:20]}...")
        
        # Base64 decode et (eğitim amaçlı)
        import base64
        import json
        
        try:
            # Header'ı decode et
            header_decoded = base64.urlsafe_b64decode(parts[0] + '=' * (4 - len(parts[0]) % 4))
            header_json = json.loads(header_decoded)
            print(f"\n📝 HEADER (decoded):")
            print(f"   {json.dumps(header_json, indent=2)}")
            
            # Payload'ı decode et
            payload_decoded = base64.urlsafe_b64decode(parts[1] + '=' * (4 - len(parts[1]) % 4))
            payload_json = json.loads(payload_decoded)
            print(f"\n📝 PAYLOAD (decoded):")
            print(f"   {json.dumps(payload_json, indent=2)}")
            
        except Exception as e:
            print(f"❌ Decode hatası: {e}")

def main():
    """Ana menü"""
    client = JWTClient()
    
    print("=" * 50)
    print("🔐 JWT TOKEN İSTEMCİSİ")
    print("=" * 50)
    
    # Sunucu kontrolü
    try:
        response = requests.get(BASE_URL, timeout=2)
        print("✅ Sunucu erişilebilir")
    except:
        print("❌ Sunucu çalışmıyor! Önce sunucuyu başlat:")
        print("   uvicorn server_jwt:app --reload --port 8001")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("MENÜ:")
        print("  1. Giriş Yap (yonetici/admin123)")
        print("  2. Giriş Yap (personel/123)")
        print("  3. Profilimi Görüntüle")
        print("  4. Token'ı Doğrula")
        print("  5. Korumalı Endpoint'e Eriş")
        print("  6. Tüm Kullanıcıları Listele (Yönetici)")
        print("  7. Token Yapısını İncele")
        print("  8. Manuel Token Doğrula")
        print("  9. Çıkış")
        print("=" * 50)
        
        choice = input("Seçiminiz (1-9): ").strip()
        
        if choice == "1":
            client.login("yonetici", "admin123")
        elif choice == "2":
            client.login("personel", "123")
        elif choice == "3":
            client.get_profile()
        elif choice == "4":
            client.validate_token()
        elif choice == "5":
            client.access_protected_endpoint()
        elif choice == "6":
            client.list_users()
        elif choice == "7":
            client.decode_token_parts()
        elif choice == "8":
            token = input("Token girin: ").strip()
            client.validate_token(token)
        elif choice == "9":
            print("👋 Çıkış yapılıyor...")
            break
        else:
            print("❌ Geçersiz seçim!")
        
        input("\nDevam etmek için Enter'a basın...")

if __name__ == "__main__":
    main()