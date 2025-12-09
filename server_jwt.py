"""
JWT Token Kullanan Authentication Sunucusu
Çalıştırma: uvicorn server_jwt:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import jwt
from decouple import config
import uvicorn

# JWT ayarlarını .env'den al
SECRET_KEY = config("JWT_SECRET_KEY")
ALGORITHM = config("JWT_ALGORITHM", default="HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(config("JWT_EXPIRE_MINUTES", default=60))

# Demo kullanıcılar (eczane otomasyonundan)
users_db = {
    config("ADMIN_USERNAME"): {
        "username": config("ADMIN_USERNAME"),
        "password": config("ADMIN_PASSWORD"),
        "role": "Yönetici",
        "full_name": "Eczane Yöneticisi"
    },
    config("PERSONEL_USERNAME"): {
        "username": config("PERSONEL_USERNAME"),
        "password": config("PERSONEL_PASSWORD"),
        "role": "Personel",
        "full_name": "Eczane Personeli"
    }
}

# FastAPI uygulaması
app = FastAPI(
    title="Eczane JWT Auth API",
    description="Eczane otomasyonu için JWT token servisi",
    version="1.0.0"
)

# Bearer token şeması
security = HTTPBearer()

# =============== MODELLER ===============
class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user_info: dict

class UserInfo(BaseModel):
    username: str
    role: str
    full_name: str

class TokenData(BaseModel):
    username: str
    role: str

class ValidateRequest(BaseModel):
    token: str

class ValidateResponse(BaseModel):
    valid: bool
    username: Optional[str] = None
    role: Optional[str] = None
    message: Optional[str] = None

# =============== JWT FONKSİYONLARI ===============
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT token oluştur"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),  # issued at
        "iss": "eczane-auth-server"  # issuer
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    """Token'ı decode et ve doğrula"""
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "sub"]}
        )
        username = payload.get("sub")
        if username is None:
            return {"error": "Token'da kullanıcı adı yok"}
        return payload
    except jwt.ExpiredSignatureError:
        return {"error": "Token süresi dolmuş"}
    except jwt.InvalidTokenError as e:
        return {"error": f"Geçersiz token: {str(e)}"}
    except Exception as e:
        return {"error": f"Token doğrulama hatası: {str(e)}"}

# Token doğrulama fonksiyonu (dependency)
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    
    if isinstance(payload, dict) and "error" in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=payload["error"]
        )
    
    return payload

# Kullanıcı doğrulama
def authenticate_user(username: str, password: str):
    user = users_db.get(username)
    if not user or user["password"] != password:
        return False
    return user

# =============== ENDPOINT'LER ===============
@app.get("/")
def read_root():
    return {
        "message": "🏥 Eczane JWT Authentication API",
        "endpoints": {
            "login": "POST /login (username, password)",
            "profile": "GET /profile (Bearer token gerekli)",
            "validate": "POST /validate (token doğrulama)",
            "users": "GET /users (tüm kullanıcılar)"
        },
        "docs": "/docs veya /redoc",
        "status": "active"
    }

@app.post("/login", response_model=Token)
def login(request: LoginRequest):
    """Kullanıcı girişi yap ve JWT token al"""
    user = authenticate_user(request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Token oluştur
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"],
            "full_name": user["full_name"]
        },
        expires_delta=access_token_expires
    )
    
    # Kullanıcı bilgilerini token'dan çıkar (şifre hariç)
    user_info = {
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"]
    }
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_info": user_info
    }

@app.get("/profile", response_model=UserInfo)
def get_profile(payload: dict = Depends(verify_token)):
    """Token ile kullanıcı profilini getir"""
    username = payload.get("sub")
    user = users_db.get(username)
    
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    return {
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"]
    }

@app.post("/validate", response_model=ValidateResponse)
def validate_token(request: ValidateRequest):
    """Token'ı doğrula (manuel kontrol için)"""
    payload = decode_token(request.token)
    
    if isinstance(payload, dict) and "error" in payload:
        return ValidateResponse(
            valid=False,
            message=payload["error"]
        )
    
    return ValidateResponse(
        valid=True,
        username=payload.get("sub"),
        role=payload.get("role"),
        message="Token geçerli"
    )

@app.get("/users")
def get_users(payload: dict = Depends(verify_token)):
    """Tüm kullanıcıları listele (şifreler hariç)"""
    # Sadece yönetici erişebilir
    if payload.get("role") != "Yönetici":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için yetkiniz yok"
        )
    
    users_list = []
    for username, user in users_db.items():
        users_list.append({
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"]
        })
    
    return {
        "count": len(users_list),
        "users": users_list
    }

@app.get("/protected")
def protected_endpoint(payload: dict = Depends(verify_token)):
    """Korumalı endpoint örneği"""
    return {
        "message": f"Hoş geldiniz {payload.get('full_name', 'Kullanıcı')}!",
        "user_data": {
            "username": payload.get("sub"),
            "role": payload.get("role"),
            "token_issued": datetime.fromtimestamp(payload.get("iat")).isoformat() if payload.get("iat") else None,
            "token_expires": datetime.fromtimestamp(payload.get("exp")).isoformat() if payload.get("exp") else None
        },
        "timestamp": datetime.now().isoformat()
    }

# =============== ÇALIŞTIRMA ===============
if __name__ == "__main__":
    print(f"🔐 JWT Sunucusu başlatılıyor...")
    print(f"   Port: 8001")
    print(f"   Secret Key: {SECRET_KEY[:10]}...")
    print(f"   Algorithm: {ALGORITHM}")
    print(f"   Token Süresi: {ACCESS_TOKEN_EXPIRE_MINUTES} dakika")
    print(f"   Kullanıcılar: {list(users_db.keys())}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001,
        reload=True
    )