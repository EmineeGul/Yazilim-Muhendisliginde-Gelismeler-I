from flask import Flask, request, redirect, url_for, session, flash, render_template_string, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "cok-gizli-anahtar"
API_URL = os.environ.get("API_URL", "http://localhost:8000")

# --- HTML ŞABLONLARI ---

MAIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Eczane Otomasyonu</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .stock-critical { background-color: #ffe6e6 !important; }
        .stock-low { background-color: #fff3cd !important; }
        .stock-ok { background-color: #d1e7dd !important; }
        .alert-badge { 
            animation: pulse 2s infinite;
            cursor: pointer;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body class="bg-light">

<nav class="navbar navbar-dark bg-primary mb-4">
    <div class="container">
        <span class="navbar-brand h1">💊 Eczane Sistemi (İTS & Depo)</span>
        {% if session.get('token') %}
        <div class="d-flex align-items-center text-white">
            <!-- Uyarı Badge'i -->
            {% if low_stock_count > 0 %}
            <div class="me-3 position-relative">
                <span class="alert-badge badge bg-danger rounded-pill" 
                      data-bs-toggle="modal" data-bs-target="#alertsModal">
                    ⚠️ {{ low_stock_count }}
                </span>
            </div>
            {% endif %}
            
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
    <!-- Giriş Formu -->
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
    
    <!-- YENİ: Uyarılar Modal'ı -->
    <div class="modal fade" id="alertsModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-warning">
                    <h5 class="modal-title">⚠️ Stok Uyarıları</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card mb-3">
                                <div class="card-header bg-danger text-white">
                                    <h6>⛔ Kritik Stok (≤ 5 adet)</h6>
                                </div>
                                <div class="card-body">
                                    {% if critical_drugs %}
                                    <ul class="list-group">
                                        {% for d in critical_drugs %}
                                        <li class="list-group-item d-flex justify-content-between">
                                            <span>{{ d.name }}</span>
                                            <span class="badge bg-danger">{{ d.stock_quantity }} adet</span>
                                        </li>
                                        {% endfor %}
                                    </ul>
                                    {% else %}
                                    <p class="text-muted">Kritik stok yok</p>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card mb-3">
                                <div class="card-header bg-warning">
                                    <h6>⚠️ Düşük Stok</h6>
                                </div>
                                <div class="card-body">
                                    {% if low_drugs %}
                                    <ul class="list-group">
                                        {% for d in low_drugs %}
                                        <li class="list-group-item d-flex justify-content-between">
                                            <span>{{ d.name }}</span>
                                            <span class="badge bg-warning">{{ d.stock_quantity }} adet</span>
                                            <small>Eşik: {{ d.low_stock_threshold }}</small>
                                        </li>
                                        {% endfor %}
                                    </ul>
                                    {% else %}
                                    <p class="text-muted">Düşük stok yok</p>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-3">
                        <button class="btn btn-primary btn-sm" onclick="manualStockCheck()">
                            🔄 Manuel Kontrol
                        </button>
                        <button class="btn btn-info btn-sm" onclick="viewAlertHistory()">
                            📋 Uyarı Geçmişi
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Yeni İlaç Modal -->
    <div class="modal fade" id="addDrugModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header bg-success text-white">
                    <h5 class="modal-title">➕ Yeni İlaç Ekle</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form action="/add_drug" method="POST" id="addDrugForm">
                        <input type="text" name="name" class="form-control mb-2" placeholder="İlaç Adı" required>
                        <input type="text" name="active_ingredient" class="form-control mb-2" placeholder="Etken Madde" required>
                        <input type="number" step="0.01" name="price" class="form-control mb-2" placeholder="Fiyat" required>
                        <input type="number" name="stock_quantity" class="form-control mb-2" placeholder="Başlangıç Stoku" required>
                        <input type="number" name="low_stock_threshold" class="form-control mb-2" placeholder="Uyarı Eşiği (Varsayılan: 10)" value="10">
                        <button type="submit" class="btn btn-success w-100">Kaydet</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <!-- Tab Menü -->
    <ul class="nav nav-tabs" id="myTab" role="tablist">
        <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#drugs">💊 İlaç & Stok</button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#customers">👥 Müşteriler</button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#reports">📊 Raporlar</button></li>
        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#alerts">🚨 Uyarılar</button></li>
    </ul>

    <div class="tab-content bg-white border border-top-0 p-4 shadow-sm" id="myTabContent">
        
        <!-- İLAÇ TABI -->
        <div class="tab-pane fade show active" id="drugs">
            <div class="row mb-3">
                <div class="col-md-8">
                    <h5>📦 Stok Listesi
                        <span class="badge bg-info ms-2">Toplam: {{ drugs|length }} ilaç</span>
                        {% if low_stock_count > 0 %}
                        <span class="badge bg-warning ms-1">Düşük: {{ low_stock_count }}</span>
                        {% endif %}
                        {% if critical_stock_count > 0 %}
                        <span class="badge bg-danger ms-1">Kritik: {{ critical_stock_count }}</span>
                        {% endif %}
                    </h5>
                </div>
                <div class="col-md-4 text-end">
                    {% if session['role'] == 'Yönetici' %}
                    <button class="btn btn-success btn-sm" data-bs-toggle="modal" data-bs-target="#addDrugModal">
                        ➕ Yeni İlaç
                    </button>
                    <button class="btn btn-warning btn-sm" onclick="checkStock()">
                        🔍 Stok Kontrolü
                    </button>
                    {% endif %}
                </div>
            </div>

            <!-- İlaç Tablosu -->
            <table class="table table-hover border">
                <thead class="table-light">
                    <tr>
                        <th>İlaç</th>
                        <th>Fiyat</th>
                        <th>Stok</th>
                        <th>Eşik</th>
                        <th>Durum</th>
                        <th>İşlem</th>
                    </tr>
                </thead>
                <tbody>
                {% for d in drugs %}
                <tr class="
                    {% if d.stock_quantity <= 5 %}stock-critical
                    {% elif d.stock_quantity <= d.low_stock_threshold %}stock-low
                    {% else %}stock-ok{% endif %}">
                    <td>
                        <strong>{{ d.name }}</strong><br>
                        <small class="text-muted">{{ d.active_ingredient }}</small>
                    </td>
                    <td>{{ d.price }} TL</td>
                    <td>
                        <span class="badge 
                            {% if d.stock_quantity <= 5 %}bg-danger
                            {% elif d.stock_quantity <= d.low_stock_threshold %}bg-warning
                            {% else %}bg-success{% endif %}">
                            {{ d.stock_quantity }}
                        </span>
                    </td>
                    <td>
                        {% if session['role'] == 'Yönetici' %}
                        <form action="/update_threshold" method="POST" class="d-flex">
                            <input type="hidden" name="drug_id" value="{{ d.id }}">
                            <input type="number" name="threshold" value="{{ d.low_stock_threshold }}" 
                                   class="form-control form-control-sm" style="width: 60px;">
                            <button type="submit" class="btn btn-sm btn-outline-secondary ms-1">✓</button>
                        </form>
                        {% else %}
                        {{ d.low_stock_threshold }}
                        {% endif %}
                    </td>
                    <td>
                        {% if d.stock_quantity <= 5 %}
                        <span class="badge bg-danger">KRİTİK</span>
                        {% elif d.stock_quantity <= d.low_stock_threshold %}
                        <span class="badge bg-warning">DÜŞÜK</span>
                        {% else %}
                        <span class="badge bg-success">NORMAL</span>
                        {% endif %}
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

            <!-- Stok Grafiği -->
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">📊 Stok Durumu</div>
                        <div class="card-body">
                            <canvas id="stockChart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">ℹ️ Stok İstatistikleri</div>
                        <div class="card-body">
                            <p><strong>Toplam Stok Değeri:</strong> {{ stock_report.total_stock_value|round(2) }} TL</p>
                            <p><strong>Ortalama Stok:</strong> {{ (stock_report.total_stock_value / drugs|length)|round(2) if drugs|length > 0 else 0 }} TL/ilaç</p>
                            <p><strong>En Düşük Stoklu:</strong> 
                                {% if drugs %}
                                    {% set min_stock = drugs|min(attribute='stock_quantity') %}
                                    {{ min_stock.name }} ({{ min_stock.stock_quantity }} adet)
                                {% endif %}
                            </p>
                            <p><strong>En Yüksek Stoklu:</strong>
                                {% if drugs %}
                                    {% set max_stock = drugs|max(attribute='stock_quantity') %}
                                    {{ max_stock.name }} ({{ max_stock.stock_quantity }} adet)
                                {% endif %}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- MÜŞTERİLER TABI -->
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

        <!-- RAPORLAR TABI -->
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

        <!-- YENİ: UYARILAR TABI -->
        <div class="tab-pane fade" id="alerts">
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header bg-warning">⚙️ Uyarı Ayarları</div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label class="form-label">Kontrol Aralığı (dakika)</label>
                                <select id="checkInterval" class="form-select">
                                    <option value="15">15 dakika</option>
                                    <option value="30">30 dakika</option>
                                    <option value="60" selected>60 dakika</option>
                                    <option value="120">2 saat</option>
                                    <option value="360">6 saat</option>
                                    <option value="720">12 saat</option>
                                    <option value="1440">24 saat</option>
                                </select>
                            </div>
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" id="enableEmail">
                                <label class="form-check-label" for="enableEmail">E-posta uyarıları</label>
                            </div>
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" id="enableSMS">
                                <label class="form-check-label" for="enableSMS">SMS uyarıları</label>
                            </div>
                            <div class="form-check mb-3">
                                <input class="form-check-input" type="checkbox" id="enableAutoOrder">
                                <label class="form-check-label" for="enableAutoOrder">Otomatik sipariş</label>
                            </div>
                            <button class="btn btn-warning w-100" onclick="saveAlertSettings()">Ayarları Kaydet</button>
                        </div>
                    </div>
                    
                    <div class="card mt-3">
                        <div class="card-header bg-info">🔧 Hızlı İşlemler</div>
                        <div class="card-body">
                            <button class="btn btn-primary w-100 mb-2" onclick="manualStockCheck()">
                                🔄 Manuel Stok Kontrolü
                            </button>
                            <button class="btn btn-secondary w-100 mb-2" onclick="getAlertHistory()">
                                📋 Uyarı Geçmişini Getir
                            </button>
                            <button class="btn btn-success w-100" onclick="autoOrderLowStock()">
                                📦 Düşük Stoklara Otomatik Sipariş
                            </button>
                        </div>
                    </div>
                </div>

                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header bg-danger text-white">🚨 Uyarı Geçmişi</div>
                        <div class="card-body">
                            <div id="alertHistory">
                                <p class="text-muted">Uyarı geçmişi yükleniyor...</p>
                            </div>
                        </div>
                    </div>

                    <div class="card mt-3">
                        <div class="card-header bg-success text-white">📈 Stok Analizi</div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="card bg-light">
                                        <div class="card-body text-center">
                                            <h5>Kritik Stok</h5>
                                            <h2 class="text-danger">{{ critical_stock_count }}</h2>
                                            <small>≤ 5 adet</small>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card bg-light">
                                        <div class="card-body text-center">
                                            <h5>Düşük Stok</h5>
                                            <h2 class="text-warning">{{ low_stock_count }}</h2>
                                            <small>≤ eşik değeri</small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="mt-3">
                                <h6>Önerilen Eylemler:</h6>
                                <ul>
                                    {% if critical_stock_count > 0 %}
                                    <li class="text-danger">⛔ <strong>ACİL:</strong> {{ critical_stock_count }} ilaç kritik stokta!</li>
                                    {% endif %}
                                    {% if low_stock_count > 0 %}
                                    <li class="text-warning">⚠️ {{ low_stock_count }} ilaç düşük stokta, sipariş verin.</li>
                                    {% endif %}
                                    {% if critical_stock_count == 0 and low_stock_count == 0 %}
                                    <li class="text-success">✅ Stok durumu normal.</li>
                                    {% endif %}
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>
    {% endif %}
</div>

<script>
// JavaScript Fonksiyonları
function manualStockCheck() {
    fetch('/api/check_stock')
        .then(response => response.json())
        .then(data => {
            alert(data.message || 'Stok kontrolü başlatıldı!');
            setTimeout(() => location.reload(), 1000);
        })
        .catch(error => {
            console.error('Hata:', error);
            alert('Stok kontrolü başlatılamadı');
        });
}

function checkStock() {
    fetch('/api/check_stock')
        .then(response => response.json())
        .then(data => {
            alert('Stok kontrolü tamamlandı!');
            location.reload();
        });
}

function viewAlertHistory() {
    fetch('/api/alert_history')
        .then(response => response.json())
        .then(data => {
            const historyDiv = document.getElementById('alertHistory');
            if (data.length === 0) {
                historyDiv.innerHTML = '<p class="text-muted">Henüz uyarı yok.</p>';
                return;
            }
            
            let html = '<table class="table table-sm"><thead><tr><th>Tarih</th><th>Tip</th><th>İlaç Sayısı</th></tr></thead><tbody>';
            data.slice(-10).reverse().forEach(alert => {
                const date = new Date(alert.timestamp).toLocaleString('tr-TR');
                const typeBadge = alert.type === 'critical' ? 
                    '<span class="badge bg-danger">KRİTİK</span>' : 
                    '<span class="badge bg-warning">DÜŞÜK</span>';
                
                html += `<tr>
                    <td>${date}</td>
                    <td>${typeBadge}</td>
                    <td>${alert.drug_count} ilaç</td>
                </tr>`;
            });
            html += '</tbody></table>';
            historyDiv.innerHTML = html;
        });
}

function getAlertHistory() {
    viewAlertHistory();
}

function saveAlertSettings() {
    const settings = {
        check_interval: document.getElementById('checkInterval').value,
        enable_email: document.getElementById('enableEmail').checked,
        enable_sms: document.getElementById('enableSMS').checked,
        enable_auto_order: document.getElementById('enableAutoOrder').checked
    };
    
    alert('Ayarlar kaydedildi (demo modu). Gerçek uygulamada API\'ye gönderilecek.');
    console.log('Kaydedilen ayarlar:', settings);
}

function autoOrderLowStock() {
    if (confirm('Düşük stoklu tüm ilaçlara otomatik sipariş verilsin mi?')) {
        alert('Otomatik siparişler oluşturuluyor... (demo modu)');
        // Gerçek uygulamada API çağrısı yapılacak
    }
}

// Sayfa yüklendiğinde stok grafiğini çiz
document.addEventListener('DOMContentLoaded', function() {
    // Stok grafiği verileri - DÜZELTİLDİ!
    const drugNames = {{ drug_names|tojson if drug_names else '[]' }};
    const stockQuantities = {{ stock_quantities|tojson if stock_quantities else '[]' }};
    
    if (drugNames && drugNames.length > 0 && drugNames[0] !== '') {
        const ctx = document.getElementById('stockChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: drugNames,
                datasets: [{
                    label: 'Stok Miktarı',
                    data: stockQuantities,
                    backgroundColor: stockQuantities.map(q => 
                        q <= 5 ? '#dc3545' : 
                        q <= 10 ? '#ffc107' : '#198754'
                    ),
                    borderColor: '#333',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Adet'
                        }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                }
            }
        });
    } else {
        // Grafik yoksa mesaj göster
        document.getElementById('stockChart').parentElement.innerHTML = 
            '<p class="text-muted">Grafik verisi bulunamadı veya henüz ilaç eklenmedi.</p>';
    }
    
    // Sayfa açıldığında uyarı geçmişini yükle
    if (document.getElementById('alerts').classList.contains('active')) {
        viewAlertHistory();
    }
});
</script>

</body>
</html>
"""

# Müşteri Geçmişi Şablonu
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
        # Temel verileri getir
        drugs_response = requests.get(f"{API_URL}/drugs", headers=headers)
        customers_response = requests.get(f"{API_URL}/customers", headers=headers)
        report_response = requests.get(f"{API_URL}/reports/daily", headers=headers)
        
        # Yeni endpoint'ler
        low_stock_response = requests.get(f"{API_URL}/drugs/low-stock", headers=headers)
        critical_stock_response = requests.get(f"{API_URL}/drugs/critical-stock", headers=headers)
        stock_report_response = requests.get(f"{API_URL}/reports/stock-status", headers=headers)
        
        drugs = drugs_response.json() if drugs_response.status_code == 200 else []
        customers = customers_response.json() if customers_response.status_code == 200 else []
        report = report_response.json() if report_response.status_code == 200 else {
            "total_sales_count": 0, "total_revenue": 0, "details": [], "date": "---"
        }
        
        low_drugs = low_stock_response.json() if low_stock_response.status_code == 200 else []
        critical_drugs = critical_stock_response.json() if critical_stock_response.status_code == 200 else []
        stock_report = stock_report_response.json() if stock_report_response.status_code == 200 else {
            "total_stock_value": 0, "low_stock_count": 0, "critical_stock_count": 0
        }
        
        # Grafik verileri - GÜVENLİ HALE GETİRİLDİ
        drug_names = []
        stock_quantities = []
        if drugs and len(drugs) > 0:
            drug_names = [d.get("name", "") for d in drugs]
            stock_quantities = [d.get("stock_quantity", 0) for d in drugs]
        
        # Uyarı sayıları
        low_stock_count = len(low_drugs) if low_drugs else 0
        critical_stock_count = len(critical_drugs) if critical_drugs else 0
        
    except Exception as e:
        print(f"Hata: {e}")
        drugs, customers, report = [], [], {"total_sales_count": 0, "total_revenue": 0, "details": [], "date": "---"}
        low_drugs, critical_drugs = [], []
        stock_report = {"total_stock_value": 0, "low_stock_count": 0, "critical_stock_count": 0}
        drug_names, stock_quantities = [], []
        low_stock_count, critical_stock_count = 0, 0

    return render_template_string(
        MAIN_HTML, 
        drugs=drugs, 
        customers=customers, 
        report=report,
        low_drugs=low_drugs,
        critical_drugs=critical_drugs,
        stock_report=stock_report,
        drug_names=drug_names,
        stock_quantities=stock_quantities,
        low_stock_count=low_stock_count,
        critical_stock_count=critical_stock_count
    )

@app.route("/login", methods=["POST"])
def login():
    try:
        resp = requests.post(f"{API_URL}/login", json={
            "username": request.form["username"],
            "password": request.form["password"]
        })
        if resp.status_code == 200:
            data = resp.json()
            session["token"] = data["token"]
            session["role"] = data.get("user_info", {}).get("role", data.get("role", "Personel"))
            return redirect("/")
    except Exception as e:
        print(f"Login hatası: {e}")
        flash("Giriş başarısız! Backend kapalı olabilir.", "danger")
    return redirect("/")

@app.route("/sell", methods=["POST"])
def sell():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    
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
        resp = requests.post(f"{API_URL}/order_stock", 
                           json={"drug_id": request.form["drug_id"], "quantity": 10}, 
                           headers=headers)
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
        "price": float(request.form["price"]),
        "stock_quantity": int(request.form["stock_quantity"]),
        "low_stock_threshold": int(request.form.get("low_stock_threshold", 10))
    }
    try:
        resp = requests.post(f"{API_URL}/drugs", json=payload, headers=headers)
        if resp.status_code == 201:
            flash("İlaç başarıyla eklendi", "success")
        else:
            flash("İlaç eklenemedi", "danger")
    except: flash("Bağlantı hatası", "danger")
    return redirect("/")

@app.route("/update_threshold", methods=["POST"])
def update_threshold():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        drug_id = int(request.form["drug_id"])
        threshold = int(request.form["threshold"])
        resp = requests.put(f"{API_URL}/drugs/{drug_id}/threshold?threshold={threshold}", headers=headers)
        if resp.status_code == 200:
            flash(f"Stok eşiği {threshold} olarak güncellendi", "info")
        else:
            flash("Eşik güncellenemedi", "danger")
    except: flash("Bağlantı hatası", "danger")
    return redirect("/")

@app.route("/delete_drug", methods=["POST"])
def delete_drug():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        resp = requests.delete(f"{API_URL}/drugs/{request.form['drug_id']}", headers=headers)
        if resp.status_code in [200, 204]:
            flash("İlaç silindi", "warning")
        else:
            flash("İlaç silinemedi", "danger")
    except: flash("Bağlantı hatası", "danger")
    return redirect("/")

@app.route("/add_customer", methods=["POST"])
def add_customer():
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        resp = requests.post(f"{API_URL}/customers", json=request.form, headers=headers)
        if resp.status_code == 200:
            flash("Müşteri başarıyla eklendi", "success")
        else:
            flash("Müşteri eklenemedi", "danger")
    except: flash("Bağlantı hatası", "danger")
    return redirect("/")

@app.route("/customer_history/<int:c_id>")
def customer_history(c_id):
    if "token" not in session: return redirect("/")
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        history = requests.get(f"{API_URL}/customers/{c_id}/history", headers=headers).json()
    except: history = []
    return render_template_string(HISTORY_HTML, history=history)

# YENİ API ENDPOINT'LERİ
@app.route("/api/check_stock")
def api_check_stock():
    if "token" not in session: return jsonify({"error": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        resp = requests.get(f"{API_URL}/alerts/check", headers=headers)
        return jsonify(resp.json())
    except:
        return jsonify({"error": "Backend connection failed"}), 500

@app.route("/api/alert_history")
def api_alert_history():
    if "token" not in session: return jsonify({"error": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        resp = requests.get(f"{API_URL}/alerts/history", headers=headers)
        return jsonify(resp.json())
    except:
        return jsonify({"error": "Backend connection failed"}), 500

@app.route("/api/stock_report")
def api_stock_report():
    if "token" not in session: return jsonify({"error": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        resp = requests.get(f"{API_URL}/reports/stock-status", headers=headers)
        return jsonify(resp.json())
    except:
        return jsonify({"error": "Backend connection failed"}), 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)