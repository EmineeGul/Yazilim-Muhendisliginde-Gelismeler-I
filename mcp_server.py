"""
Eczane Otomasyonu için MCP (Model Context Protocol) Server
"""
import json
from typing import List, Dict, Any
from mcp.server import Server
from mcp.types import Tool
from datetime import datetime
import sqlalchemy
from sqlalchemy.orm import Session
from database import SessionLocal, Drug, Sale, Customer, Alert

# MCP Server oluştur
app = Server("eczane-otomasyonu-mcp")

# Database session helper
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. İLAÇ ARAMA TOOL'U
@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """Kullanılabilir MCP tool'larını listele"""
    return [
        Tool(
            name="search_drugs",
            description="İlaç ismi veya etken maddeye göre arama yap",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Aranacak ilaç adı veya etken madde"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Sonuç sayısı (default: 10)",
                        "default": 10
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="check_stock",
            description="İlaç stok durumunu kontrol et",
            inputSchema={
                "type": "object",
                "properties": {
                    "drug_id": {
                        "type": "integer",
                        "description": "İlaç ID'si (isteğe bağlı)"
                    },
                    "drug_name": {
                        "type": "string",
                        "description": "İlaç ismi (isteğe bağlı)"
                    }
                }
            }
        ),
        Tool(
            name="get_low_stock_alerts",
            description="Düşük ve kritik stok uyarılarını getir",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Sonuç sayısı",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="get_daily_sales_report",
            description="Günlük satış raporunu getir",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Tarih (YYYY-MM-DD formatında, boşsa bugün)",
                        "default": ""
                    }
                }
            }
        ),
        Tool(
            name="add_drug_to_cart",
            description="Sanal sepet için ilaç ekle (demo amaçlı)",
            inputSchema={
                "type": "object",
                "properties": {
                    "drug_id": {
                        "type": "integer",
                        "description": "İlaç ID'si",
                        "required": True
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Miktar",
                        "default": 1
                    }
                }
            }
        ),
        # YENİ: Public API sorgusu yapan tool
        Tool(
            name="public_api_query",
            description="Public API'den veri çek (demo amaçlı)",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_endpoint": {
                        "type": "string",
                        "description": "API endpoint URL",
                        "default": "https://jsonplaceholder.typicode.com/todos/1"
                    }
                }
            }
        ),
        # YENİ: Toplama işlemi yapan basit tool
        Tool(
            name="toplama_islemi",
            description="İki sayıyı toplar",
            inputSchema={
                "type": "object",
                "properties": {
                    "sayi1": {
                        "type": "number",
                        "description": "İlk sayı"
                    },
                    "sayi2": {
                        "type": "number", 
                        "description": "İkinci sayı"
                    }
                },
                "required": ["sayi1", "sayi2"]
            }
        )
    ]

# 2. TOOL ÇALIŞTIRMA İŞLEMLERİ
@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool'larını çalıştır"""
    
    if name == "toplama_islemi":
        # Basit toplama işlemi
        sayi1 = arguments.get("sayi1", 0)
        sayi2 = arguments.get("sayi2", 0)
        toplam = sayi1 + sayi2
        
        return {
            "content": [{
                "type": "text",
                "text": f"Toplama işlemi sonucu: {sayi1} + {sayi2} = {toplam}"
            }]
        }
    
    elif name == "public_api_query":
        # Public API sorgusu
        import requests
        api_endpoint = arguments.get("api_endpoint", "https://jsonplaceholder.typicode.com/todos/1")
        
        try:
            response = requests.get(api_endpoint, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": f"✅ Public API'den veri alındı:\nEndpoint: {api_endpoint}\n\n" +
                               f"Response (ilk 200 karakter):\n{str(data)[:200]}..."
                    }]
                }
            else:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"❌ API isteği başarısız. Status code: {response.status_code}"
                    }]
                }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ API sorgusu hatası: {str(e)}"
                }]
            }
    
    # Diğer tool'lar için database bağlantısı
    db = SessionLocal()
    
    try:
        if name == "search_drugs":
            search_term = arguments.get("search_term", "")
            limit = arguments.get("limit", 10)
            
            # İlaçları ara
            drugs = db.query(Drug).filter(
                (Drug.name.ilike(f"%{search_term}%")) | 
                (Drug.active_ingredient.ilike(f"%{search_term}%"))
            ).limit(limit).all()
            
            if not drugs:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"'{search_term}' ile ilgili ilaç bulunamadı."
                    }]
                }
            
            # Formatla
            drug_list = []
            for drug in drugs:
                stock_status = "🟢 NORMAL"
                if drug.stock_quantity <= 5:
                    stock_status = "🔴 KRİTİK"
                elif drug.stock_quantity <= drug.low_stock_threshold:
                    stock_status = "🟡 DÜŞÜK"
                
                drug_list.append({
                    "id": drug.id,
                    "name": drug.name,
                    "active_ingredient": drug.active_ingredient,
                    "price": f"{drug.price} TL",
                    "stock": f"{drug.stock_quantity} adet",
                    "status": stock_status,
                    "threshold": drug.low_stock_threshold
                })
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"'{search_term}' için {len(drug_list)} sonuç bulundu:\n\n" +
                           "\n".join([f"• {d['name']} ({d['active_ingredient']}) - {d['price']} - {d['stock']} - {d['status']}" for d in drug_list])
                }]
            }
        
        elif name == "check_stock":
            drug_id = arguments.get("drug_id")
            drug_name = arguments.get("drug_name")
            
            drug = None
            if drug_id:
                drug = db.query(Drug).filter(Drug.id == drug_id).first()
            elif drug_name:
                drug = db.query(Drug).filter(Drug.name.ilike(f"%{drug_name}%")).first()
            
            if not drug:
                return {
                    "content": [{
                        "type": "text",
                        "text": "İlaç bulunamadı."
                    }]
                }
            
            stock_status = "NORMAL"
            if drug.stock_quantity <= 5:
                stock_status = "KRİTİK STOK! ⚠️"
            elif drug.stock_quantity <= drug.low_stock_threshold:
                stock_status = "DÜŞÜK STOK"
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"🏥 **{drug.name}** Stok Durumu:\n" +
                           f"• Etken Madde: {drug.active_ingredient}\n" +
                           f"• Fiyat: {drug.price} TL\n" +
                           f"• Mevcut Stok: {drug.stock_quantity} adet\n" +
                           f"• Stok Eşiği: {drug.low_stock_threshold} adet\n" +
                           f"• Durum: **{stock_status}**\n" +
                           f"• Açıklama: {drug.description or 'Açıklama yok'}"
                }]
            }
        
        elif name == "get_low_stock_alerts":
            limit = arguments.get("limit", 20)
            
            # Düşük stoklu ilaçlar
            low_stock_drugs = db.query(Drug).filter(
                Drug.stock_quantity <= Drug.low_stock_threshold
            ).order_by(Drug.stock_quantity).limit(limit).all()
            
            critical_drugs = [d for d in low_stock_drugs if d.stock_quantity <= 5]
            warning_drugs = [d for d in low_stock_drugs if d.stock_quantity > 5]
            
            response_text = f"📊 **STOK UYARI RAPORU**\n\n"
            
            if critical_drugs:
                response_text += "🔴 **KRİTİK STOK (<5 adet):**\n"
                for drug in critical_drugs:
                    response_text += f"• {drug.name}: {drug.stock_quantity} adet (Eşik: {drug.low_stock_threshold})\n"
            
            if warning_drugs:
                response_text += "\n🟡 **DÜŞÜK STOK:**\n"
                for drug in warning_drugs:
                    response_text += f"• {drug.name}: {drug.stock_quantity} adet (Eşik: {drug.low_stock_threshold})\n"
            
            if not low_stock_drugs:
                response_text += "✅ Tüm ilaçların stok durumu normal."
            
            return {
                "content": [{
                    "type": "text",
                    "text": response_text
                }]
            }
        
        elif name == "get_daily_sales_report":
            from datetime import date, datetime
            
            report_date = arguments.get("date", "")
            if report_date:
                target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
            else:
                target_date = date.today()
            
            # Bugünkü satışlar
            sales = db.query(Sale).filter(
                sqlalchemy.func.date(Sale.sale_date) == target_date
            ).all()
            
            total_revenue = sum(float(s.total_price) for s in sales)
            total_quantity = sum(s.quantity for s in sales)
            
            # Satış detayları
            details = []
            for sale in sales:
                drug = db.query(Drug).filter(Drug.id == sale.drug_id).first()
                details.append({
                    "drug": drug.name if drug else "Bilinmeyen",
                    "quantity": sale.quantity,
                    "total": float(sale.total_price)
                })
            
            response_text = (
                f"📈 **GÜNLÜK SATIŞ RAPORU**\n"
                f"• Tarih: {target_date.strftime('%d.%m.%Y')}\n"
                f"• Toplam Satış: {len(sales)} adet\n"
                f"• Toplam Ciro: {total_revenue:.2f} TL\n"
                f"• Toplam Miktar: {total_quantity} adet\n\n"
            )
            
            if details:
                response_text += "**Satış Detayları:**\n"
                for d in details:
                    response_text += f"• {d['drug']}: {d['quantity']} adet - {d['total']:.2f} TL\n"
            else:
                response_text += "Bugün satış yapılmamış."
            
            return {
                "content": [{
                    "type": "text",
                    "text": response_text
                }]
            }
        
        elif name == "add_drug_to_cart":
            # Demo amaçlı sanal sepet
            drug_id = arguments.get("drug_id")
            quantity = arguments.get("quantity", 1)
            
            drug = db.query(Drug).filter(Drug.id == drug_id).first()
            if not drug:
                return {
                    "content": [{
                        "type": "text",
                        "text": "İlaç bulunamadı."
                    }]
                }
            
            total_price = drug.price * quantity
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"🛒 **SEPETE EKLENDİ:**\n" +
                           f"• İlaç: {drug.name}\n" +
                           f"• Miktar: {quantity} adet\n" +
                           f"• Birim Fiyat: {drug.price} TL\n" +
                           f"• Toplam: {total_price:.2f} TL\n" +
                           f"• Mevcut Stok: {drug.stock_quantity} adet\n\n" +
                           f"(Demo modu - Gerçek satış yapılmadı)"
                }]
            }
        
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Bilinmeyen tool: {name}"
                }]
            }
    
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Hata oluştu: {str(e)}"
            }]
        }
    finally:
        db.close()

# MCP Server'ı başlatmak için - DÜZELTİLDİ!
if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        """Basit MCP server - Docker için düzeltildi"""
        print("🚀 Eczane MCP Server başlatılıyor...", file=sys.stderr)
        print(f"📋 Tool sayısı: 7", file=sys.stderr)
        print(f"✅ Toplama tool: toplama_islemi", file=sys.stderr)
        print(f"🌐 Public API tool: public_api_query", file=sys.stderr)
        
        # Stdio modunda çalış
        from mcp.server import stdio
        async with stdio.stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 MCP Server durduruluyor...", file=sys.stderr)