from flask import Flask, request, redirect, url_for, session, flash, render_template_string
import requests
import os

app = Flask(__name__)
app.secret_key = "cok-gizli-anahtar"

# Docker içindeyken backend ismini kullan, yoksa localhost
API_URL = os.environ.get("API_URL", "http://localhost:8000")

# --- HTML ŞABLONU (GİRİŞ VE PANEL TEK YERDE) ---
MAIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Eczane Otomasyonu</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</head>
<body class="bg-light">

<nav class="navbar navbar-dark bg-primary mb-4">
    <div class="container">
        <span class="navbar-brand h1">💊 Eczane Sistemi (İTS & Depo)</span>
        {% if session.get('token') %}
        <div class="d-flex align-items-center text-white">
            <span class="me-3">{{ session['role'] }}</span>
            <a href="/logout" class="btn btn-danger btn-sm">Çıkış</a>
        </div>
        {% endif %}
    </div>
</nav>

<div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
            <div class="alert alert-{{ 'success' if category=='success' else 'danger' }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% if not session.get('token') %}
    <div class="row justify-content-center">
        <div class="col-md-4">
            <div class="card shadow">
                <div class="card-header bg-white text-center"><h4>Giriş Yap</h4></div>
                <div class="card-body">
                    <form action="/login" method="POST">
                        <input type="text" name="username" class="form-control mb-3" placeholder="Kullanıcı Adı" required>
                        <input type="password" name="password" class="form-control mb-3" placeholder="Şifre" required>
                        <button class="btn btn-primary w-100">Giriş</button>
                    </form>
                    <div class="mt-3 small text-muted text-center">
                        Demo: yonetici / admin123 <br> personel / 123
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    {% else %}
    
    <ul class="nav nav-tabs" id="myTab" role="tablist">
        <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#drugs">💊 İlaç & Stok</button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#customers">👥 Müşteriler</button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#reports">📊 Raporlar</button></li>
    </ul>

    <div class="tab-content bg-white border border-top-0 p-4 shadow-sm" id="myTabContent">
        
        <div class="tab-pane fade show active" id="drugs">
            <div class="row">
                {% if session['role'] == 'Yönetici' %}
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-header bg-success text-white">Yeni İlaç Kaydı</div>
                        <div class="card-body">
                            <form action="/add_drug" method="POST">
                                <input type="text" name="name" class="form-control mb-2" placeholder="İlaç Adı" required>
                                <input type="text" name="active_ingredient" class="form-control mb-2" placeholder="Etken Madde" required>
                                <div class="row">
                                    <div class="col"><input type="number" name="price" class="form-control mb-2" placeholder="Fiyat" required></div>
                                    <div class="col"><input type="number" name="stock_quantity" class="form-control mb-2" placeholder="Stok" required></div>
                                </div>
                                <button class="btn btn-success w-100">Kaydet</button>
                            </form>
                        </div>
                    </div>
                </div>
                {% endif %}

                <div class="{{ 'col-md-8' if session['role'] == 'Yönetici' else 'col-md-12' }}">
                    <h5>📦 Stok Listesi</h5>
                    <table class="table table-hover border">
                        <thead class="table-light"><tr><th>İlaç</th><th>Fiyat</th><th>Stok</th><th>İşlem</th></tr></thead>
                        <tbody>
                        {% for d in drugs %}
                        <tr class="{{ 'table-danger' if d.stock_quantity < 10 else '' }}">
                            <td>{{ d.name }} <br><small class="text-muted">{{ d.active_ingredient }}</small></td>
                            <td>{{ d.price }} TL</td>
                            <td>
                                <span class="badge {{ 'bg-danger' if d.stock_quantity < 10 else 'bg-success' }}">
                                    {{ d.stock_quantity }}
                                </span>
                            </td>
                            <td>
                                <div class="d-flex gap-1">
                                    <form action="/sell" method="POST" class="d-flex align-items-center">
                                        <input type="hidden" name="drug_id" value="{{ d.id }}">
                                        <select name="customer_id" class="form-select form-select-sm me-1" style="width:110px;">
                                            <option value="">Müşterisiz</option>
                                            {% for c in customers %}
                                            <option value="{{ c.id }}">{{ c.name }}</option>
                                            {% endfor %}
                                        </select>
                                        <button class="btn btn-primary btn-sm">Sat</button>
                                    </form>
                                    
                                    <form action="/order_stock" method="POST">
                                        <input type="hidden" name="drug_id" value="{{ d.id }}">
                                        <button class="btn btn-warning btn-sm">Depo</button>
                                    </form>

                                    {% if session['role'] == 'Yönetici' %}
                                    <form action="/delete_drug" method="POST" onsubmit="return confirm('Silmek istediğine emin misin?');">
                                        <input type="hidden" name="drug_id" value="{{ d.id }}">
                                        <button class="btn btn-outline-danger btn-sm">Sil</button>
                                    </form>
                                    {% endif %}
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="tab-pane fade" id="customers">
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">Yeni Müşteri Ekle</div>
                        <div class="card-body">
                            <form action="/add_customer" method="POST">
                                <input type="text" name="name" class="form-control mb-2" placeholder="Ad Soyad" required>
                                <input type="text" name="tc_no" class="form-control mb-2" placeholder="TC Kimlik No" required>
                                <input type="text" name="phone" class="form-control mb-2" placeholder="Telefon" required>
                                <button class="btn btn-info text-white w-100">Ekle</button>
                            </form>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <h5>Müşteri Listesi & Geçmişi</h5>
                    <table class="table border">
                        <thead><tr><th>Ad Soyad</th><th>TC</th><th>Telefon</th><th>Geçmiş</th></tr></thead>
                        <tbody>
                        {% for c in customers %}
                        <tr>
                            <td>{{ c.name }}</td>
                            <td>{{ c.tc_no }}</td>
                            <td>{{ c.phone }}</td>
                            <td>
                                <a href="/customer_history/{{ c.id }}" class="btn btn-sm btn-secondary">Geçmişi Gör</a>
                            </td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="tab-pane fade" id="reports">
            <div class="text-center p-4">
                <h3>Gün Sonu Raporu</h3>
                <p class="text-muted">Tarih: {{ report.date }}</p>
                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card bg-primary text-white p-3 mb-3">
                            <h4>Toplam Satış</h4>
                            <h2>{{ report.total_sales_count }} Adet</h2>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card bg-success text-white p-3 mb-3">
                            <h4>Toplam Ciro</h4>
                            <h2>{{ report.total_revenue }} TL</h2>
                        </div>
                    </div>
                </div>
                <h5 class="mt-4 text-start">Satış Detayları (İTS Logları)</h5>
                <table class="table table-striped mt-2 border">
                    <thead><tr><th>İlaç</th><th>Tutar</th><th>İTS Onay No</th><th>Tarih</th></tr></thead>
                    <tbody>
                    {% for s in report.details %}
                    <tr>
                        <td>{{ s.drug_name }}</td>
                        <td>{{ s.total_price }} TL</td>
                        <td><span class="badge bg-dark">{{ s.its_id }}</span></td>
                        <td>{{ s.date }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="4" class="text-center">Henüz satış yapılmadı.</td></tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

    </div>
    {% endif %}
</div>
</body>
</html>
"""

# --- MÜŞTERİ GEÇMİŞİ SAYFASI ---
HISTORY_HTML = """
<!DOCTYPE html>
<html>
<head><title>Müşteri Geçmişi</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="container mt-5">
    <div class="card shadow">
        <div class="card-header bg-secondary text-white d-flex justify-content-between align-items-center">
            <h4 class="mb-0">Müşteri Satış Geçmişi</h4>
            <a href="/" class="btn btn-light btn-sm">Geri Dön</a>
        </div>
        <div class="card-body">
            <table class="table table-bordered table-striped">
                <thead><tr><th>İlaç</th><th>Adet</th><th>Tutar</th><th>Tarih</th><th>İTS No</th></tr></thead>
                <tbody>
                {% for h in history %}
                <tr>
                    <td>{{ h.drug_name }}</td>
                    <td>{{ h.quantity }}</td>
                    <td>{{ h.total_price }} TL</td>
                    <td>{{ h.date }}</td>
                    <td><span class="badge bg-info text-dark">{{ h.its_id }}</span></td>
                </tr>
                {% else %}
                <tr><td colspan="5" class="text-center text-muted">Bu müşteriye ait kayıt bulunamadı.</td></tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body></html>
"""

# --- FLASK ROTALARI ---

@app.route("/")
def index():
    if "token" not in session:
        return render_template_string(MAIN_HTML)
    
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        drugs = requests.get(f"{API_URL}/drugs", headers=headers).json()
        customers = requests.get(f"{API_URL}/customers", headers=headers).json()
        report = requests.get(f"{API_URL}/reports/daily", headers=headers).json()
    except:
        # Backend kapalıysa hata vermesin, boş göstersin
        drugs, customers, report = [], [], {"total_sales_count": 0, "total_revenue": 0, "details": [], "date": "---"}

    return render_template_string(MAIN_HTML, drugs=drugs, customers=customers, report=report)

@app.route("/login", methods=["POST"])
def login():
    try:
        resp = requests.post(f"{API_URL}/login", json=request.form)
        if resp.status_code == 200:
            data = resp.json()
            session["token"] = data["token"]
            session["role"] = data["user_info"]["role"]
            return redirect("/")
    except: pass
    flash("Giriş başarısız! Kullanıcı adı/şifre yanlış veya Sistem kapalı.", "danger")
    return redirect("/")

@app.route("/sell", methods=["POST"])
def sell():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    
    # Müşteri ID boş gelirse None yapıyoruz
    customer_id = request.form.get("customer_id")
    if not customer_id:
        customer_id = None
    
    payload = {
        "drug_id": request.form.get("drug_id"), 
        "quantity": 1,
        "customer_id": customer_id
    }
    try:
        resp = requests.post(f"{API_URL}/sales", json=payload, headers=headers)
        if resp.status_code == 201:
            flash("Satış Başarılı! İTS Onayı Alındı.", "success")
        else:
            flash(f"Hata: {resp.json().get('detail', 'Bilinmeyen hata')}", "danger")
    except: flash("Bağlantı hatası", "danger")
    return redirect("/")

@app.route("/order_stock", methods=["POST"])
def order_stock():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        resp = requests.post(f"{API_URL}/order_stock", json={"drug_id": request.form["drug_id"], "quantity": 10}, headers=headers)
        if resp.status_code == 200:
            flash(resp.json()["message"], "info")
        else:
            flash("Stok siparişi başarısız.", "danger")
    except: flash("Depo hatası", "danger")
    return redirect("/")

@app.route("/add_drug", methods=["POST"])
def add_drug():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    payload = {
        "name": request.form["name"],
        "active_ingredient": request.form["active_ingredient"],
        "price": request.form["price"],
        "stock_quantity": request.form["stock_quantity"]
    }
    requests.post(f"{API_URL}/drugs", json=payload, headers=headers)
    flash("İlaç başarıyla eklendi", "success")
    return redirect("/")

@app.route("/delete_drug", methods=["POST"])
def delete_drug():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    requests.delete(f"{API_URL}/drugs/{request.form['drug_id']}", headers=headers)
    flash("İlaç silindi", "warning")
    return redirect("/")

@app.route("/add_customer", methods=["POST"])
def add_customer():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    requests.post(f"{API_URL}/customers", json=request.form, headers=headers)
    flash("Müşteri başarıyla eklendi", "success")
    return redirect("/")

@app.route("/customer_history/<int:c_id>")
def customer_history(c_id):
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        history = requests.get(f"{API_URL}/customers/{c_id}/history", headers=headers).json()
    except: history = []
    return render_template_string(HISTORY_HTML, history=history)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    # DOCKER İÇİN ŞART OLAN KISIM: host="0.0.0.0"
    app.run(host="0.0.0.0", port=5000, debug=True)