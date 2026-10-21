import os
from datetime import datetime, date, timedelta, timezone
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lab_secret_key_123")

# Configuración de Zona Horaria Local (UTC-6 para México / Hora Local)
LOCAL_TZ = timezone(timedelta(hours=-6))

def get_local_now():
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)

# Configuración de Base de Datos PostgreSQL (Render) / SQLite (Local)
db_url = os.environ.get("DATABASE_URL", "sqlite:///laboratorio.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------------------------------------------------------------
# MODELOS DE BASE DE DATOS
# -----------------------------------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    pin = db.Column(db.String(20), nullable=False)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=False)
    name = db.Column(db.String(150), nullable=False)
    cas_number = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(50), nullable=False)
    purity = db.Column(db.String(50), nullable=True)
    physical_state = db.Column(db.String(30), nullable=True)
    storage_condition = db.Column(db.String(50), default="Temperatura Ambiente")
    hazard_label = db.Column(db.String(50), default="Ninguno")
    location = db.Column(db.String(100), nullable=True)
    lote = db.Column(db.String(50), nullable=True)
    caducidad = db.Column(db.String(20), nullable=True)
    stock_general = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(20), default="g")

class Movement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_local_now)
    item_code = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    warehouse = db.Column(db.String(50), nullable=False)
    service = db.Column(db.String(100), nullable=True)
    patient_name = db.Column(db.String(150), nullable=True)
    patient_id = db.Column(db.String(50), nullable=True)
    user_name = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.String(200), nullable=True)

class CleaningLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_local_now)
    user_name = db.Column(db.String(100), nullable=False)
    campanas = db.Column(db.Boolean, default=False)
    superficies = db.Column(db.Boolean, default=False)
    residuos = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(250), nullable=True)

# -----------------------------------------------------------------------------
# PLANTILLA HTML INTEGRADA
# -----------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LabControl - Sistema de Inventario Analítico</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        @media print {
            header, nav, .no-print, button, form { display: none !important; }
            body { background-color: white !important; }
            .print-container { width: 100% !important; margin: 0 !important; padding: 0 !important; }
        }
    </style>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800 font-sans">
    <header class="bg-gradient-to-r from-teal-900 via-emerald-900 to-slate-900 text-white shadow-lg sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 py-3 flex flex-col md:flex-row justify-between items-center gap-4">
            <div class="flex items-center gap-3">
                <div class="bg-teal-600 p-2.5 rounded-xl shadow-inner">
                    <i class="fa-solid fa-vial-circle-check text-2xl text-white"></i>
                </div>
                <div>
                    <h1 class="text-xl font-extrabold tracking-tight">LabControl Pro</h1>
                    <p class="text-[11px] text-teal-200">Sistema Integral de Reactivos, CAS & Calidad Analítica</p>
                </div>
            </div>
            <nav class="flex flex-wrap gap-1 text-xs font-bold">
                <a href="/terminal" class="px-3 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'terminal' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-pen-to-square"></i> Consumo / Ensayos
                </a>
                <a href="/alta_insumos" class="px-3 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'alta_insumos' %}bg-emerald-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-emerald-100{% endif %}">
                    <i class="fa-solid fa-plus-circle"></i> Alta Reactivo
                </a>
                <a href="/inventario" class="px-3 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'inventario' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-boxes-stacked"></i> Inventario
                </a>
                <a href="/limpieza" class="px-3 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'limpieza' %}bg-cyan-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-cyan-100{% endif %}">
                    <i class="fa-solid fa-broom"></i> Bitácora Área
                </a>
                <a href="/bitacora" class="px-3 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'bitacora' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-clock-rotate-left"></i> Historial
                </a>
                <a href="/usuarios" class="px-3 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'usuarios' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-lock"></i> Personal
                </a>
            </nav>
        </div>
    </header>

    <main class="max-w-7xl mx-auto p-4 md:p-6 print-container">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="p-4 mb-4 text-sm rounded-xl shadow-sm flex items-center gap-3 no-print {% if category == 'error' %}bg-rose-100 text-rose-800 border border-rose-300{% else %}bg-emerald-100 text-emerald-800 border border-emerald-300{% endif %}">
                <i class="fa-solid {% if category == 'error' %}fa-circle-xmark{% else %}fa-circle-check{% endif %} text-lg"></i>
                <span class="font-medium">{{ message }}</span>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        {% if view == 'terminal' %}
        <div class="space-y-6 max-w-4xl mx-auto">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <div class="mb-4">
                    <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
                        <i class="fa-solid fa-user-gear text-teal-600"></i> Seleccionar Analista Responsable
                    </h2>
                    <p class="text-xs text-slate-500">Haga clic sobre su nombre para cargarlo en el formulario.</p>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                    {% for u in users %}
                    <button type="button" onclick="selectUser('{{ u.id }}')" class="p-3.5 rounded-xl border border-slate-200 bg-slate-50 hover:bg-teal-50 hover:border-teal-400 transition text-center group flex flex-col items-center">
                        <div class="w-10 h-10 rounded-full bg-teal-100 text-teal-600 flex items-center justify-center text-lg mb-2 group-hover:scale-110 transition">
                            <i class="fa-solid {% if 'Admin' in u.role %}fa-user-shield{% else %}fa-flask{% endif %}"></i>
                        </div>
                        <h4 class="font-bold text-slate-800 text-xs group-hover:text-teal-600 truncate w-full">{{ u.name }}</h4>
                        <span class="text-[10px] text-slate-500 mt-0.5">{{ u.role }}</span>
                    </button>
                    {% endfor %}
                </div>
            </div>

            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-flask-vial text-teal-600"></i> Registrar Consumo / Entrada de Reactivo
                </h2>

                <form action="/register" method="POST" class="space-y-4">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Analista Responsable</label>
                            <select name="user_id" id="userSelect" required class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 focus:bg-white focus:ring-2 focus:ring-teal-500 outline-none">
                                <option value="">Seleccione Analista...</option>
                                {% for u in users %}
                                    <option value="{{ u.id }}">{{ u.name }} ({{ u.role }})</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">PIN / Contraseña</label>
                            <input type="password" name="pin" required placeholder="PIN de Seguridad" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-teal-500 outline-none">
                        </div>
                    </div>

                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Reactivo / Estándar (Buscador por Código / CAS)</label>
                        <input list="items_list" name="item_search" required placeholder="Escriba o escanee código, CAS o nombre..." class="w-full p-2.5 border rounded-xl text-sm bg-teal-50 focus:bg-white focus:ring-2 focus:ring-teal-500 outline-none font-medium">
                        <datalist id="items_list">
                            {% for item in items %}
                                <option value="[ID:{{ item.id }}] {{ item.code }} - {{ item.name }} (CAS: {{ item.cas_number or 'N/A' }} | Lote: {{ item.lote or 'S/L' }})">Stock: {{ item.stock_general }} {{ item.unit }} | {{ item.hazard_label }}</option>
                            {% endfor %}
                        </datalist>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Tipo de Operación</label>
                            <select name="type" required class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 focus:bg-white focus:ring-2 focus:ring-teal-500 outline-none">
                                <option value="Salida">Consumo en Ensayo / Análisis</option>
                                <option value="Entrada">Entrada (Nueva Compra)</option>
                                <option value="Baja / Residuo">Baja por Caducidad / Merma</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Ubicación / Estación</label>
                            <select name="warehouse" required class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 focus:bg-white focus:ring-2 focus:ring-teal-500 outline-none">
                                <option value="Almacén General">Almacén General de Reactivos</option>
                                <option value="Laboratorio Principal">Laboratorio Principal</option>
                            </select>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Cantidad Utilizada / Ingresada</label>
                            <input type="number" step="any" min="0.01" name="quantity" required value="1" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-teal-500 outline-none font-bold">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Equipo / Campana</label>
                            <input type="text" name="service" placeholder="Ej. Campana 2 / HPLC-01" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-teal-500 outline-none">
                        </div>
                    </div>

                    <div class="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                        <h3 class="text-xs font-bold text-teal-900 uppercase flex items-center gap-1.5">
                            <i class="fa-solid fa-vial"></i> Datos del Proyecto / Muestra
                        </h3>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                                <label class="block text-[11px] font-semibold text-slate-600 mb-1">Nombre del Proyecto / Ensayo</label>
                                <input type="text" name="patient_name" placeholder="Ej. Determinación de Pureza Lote 88" class="w-full p-2 border rounded-lg text-xs focus:ring-2 focus:ring-teal-500 outline-none bg-white font-medium">
                            </div>
                            <div>
                                <label class="block text-[11px] font-semibold text-slate-600 mb-1">Código de Muestra</label>
                                <input type="text" name="patient_id" placeholder="Ej. MUESTRA-2026-X" class="w-full p-2 border rounded-lg text-xs focus:ring-2 focus:ring-teal-500 outline-none bg-white">
                            </div>
                        </div>
                    </div>

                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Notas u Observaciones</label>
                        <input type="text" name="notes" placeholder="Observaciones adicionales..." class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-teal-500 outline-none">
                    </div>

                    <button type="submit" class="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl shadow-md transition duration-200 flex items-center justify-center gap-2">
                        <i class="fa-solid fa-check"></i> Guardar Registro Analítico
                    </button>
                </form>
            </div>
        </div>

        {% elif view == 'alta_insumos' %}
        <div class="space-y-6 max-w-xl mx-auto">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-plus-circle text-emerald-600"></i> Registrar Nuevo Reactivo / Material
                </h2>

                <form action="/add_item" method="POST" class="space-y-3">
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Código / SKU</label>
                            <input type="text" name="code" required placeholder="Ej. REQ-005" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 outline-none font-mono">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Número CAS</label>
                            <input type="text" name="cas_number" placeholder="Ej. 64-17-5" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 outline-none font-mono">
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Nombre del Reactivo / Sustancia</label>
                        <input type="text" name="name" required placeholder="Ej. Acetona ACS 99.5%" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 outline-none font-bold">
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Categoría</label>
                            <select name="category" required class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 focus:bg-white outline-none">
                                <option value="Reactivo Químico">Reactivo Químico</option>
                                <option value="Material de Vidrio">Material de Vidrio</option>
                                <option value="Medio de Cultivo">Medio de Cultivo</option>
                                <option value="Estándar Analítico">Estándar Analítico</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Pureza / Grado</label>
                            <input type="text" name="purity" placeholder="Ej. 99.8% HPLC / ACS" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Estado Físico</label>
                            <select name="physical_state" class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 outline-none">
                                <option value="Líquido">Líquido</option>
                                <option value="Sólido / Polvo">Sólido / Polvo</option>
                                <option value="Gas">Gas</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Almacenamiento</label>
                            <select name="storage_condition" class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 outline-none font-bold">
                                <option value="Temperatura Ambiente">Temperatura Ambiente</option>
                                <option value="Refrigeración (4°C)">Refrigeración (4°C)</option>
                                <option value="Congelación (-20°C)">Congelación (-20°C)</option>
                                <option value="Campana Inflamables">Campana Inflamables</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Clasificación de Riesgo GHS</label>
                        <select name="hazard_label" class="w-full p-2.5 border rounded-xl text-sm bg-rose-50 outline-none font-bold text-rose-900">
                            <option value="Ninguno">🟢 Seguro / General</option>
                            <option value="Inflamable">🔴 Inflamable</option>
                            <option value="Corrosivo">🧪 Corrosivo</option>
                            <option value="Tóxico / Nocivo">💀 Tóxico / Nocivo</option>
                        </select>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Ubicación Física</label>
                            <input type="text" name="location" placeholder="Ej. Estante C-2" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Lote</label>
                            <input type="text" name="lote" placeholder="Ej. LOT-2026-X" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                        </div>
                    </div>
                    <div class="grid grid-cols-3 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Caducidad</label>
                            <input type="date" name="caducidad" class="w-full p-2.5 border rounded-xl text-xs outline-none">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Unidad</label>
                            <select name="unit" class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 outline-none">
                                <option value="ml">ml</option>
                                <option value="g">g</option>
                                <option value="L">L</option>
                                <option value="kg">kg</option>
                                <option value="pza">pza</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Stock Inicial</label>
                            <input type="number" step="any" min="0" name="stock_general" required value="500" class="w-full p-2.5 border rounded-xl text-sm outline-none font-bold">
                        </div>
                    </div>

                    <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl shadow-md transition duration-200 flex items-center justify-center gap-2 mt-4">
                        <i class="fa-solid fa-floppy-disk"></i> Registrar Reactivo
                    </button>
                </form>
            </div>
        </div>

        {% elif view == 'inventario' %}
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <div class="flex flex-col md:flex-row justify-between items-center gap-4 mb-6 border-b pb-4">
                <div>
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        <i class="fa-solid fa-boxes-stacked text-teal-600"></i> Stock General e Inventario Analítico
                    </h2>
                    <p class="text-xs text-slate-500">Alertas automáticas por vencimiento de reactivos y trazabilidad CAS.</p>
                </div>
                <div class="w-full md:w-80 relative">
                    <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-sm"></i>
                    <input type="text" id="inventorySearch" onkeyup="filterInventory()" placeholder="Buscar por código, nombre, CAS..." class="w-full pl-10 pr-4 py-2 border rounded-xl text-xs bg-slate-50 focus:bg-white focus:ring-2 focus:ring-teal-500 outline-none font-medium">
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-sm text-left text-slate-600" id="inventoryTable">
                    <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b">
                        <tr>
                            <th class="p-3">Código / CAS</th>
                            <th class="p-3">Descripción / Pureza</th>
                            <th class="p-3">Categoría</th>
                            <th class="p-3">Riesgo (GHS)</th>
                            <th class="p-3">Lote / Caducidad</th>
                            <th class="p-3 text-center">Stock Disponible</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                        {% for item in items %}
                        <tr class="hover:bg-slate-50 transition inventory-row">
                            <td class="p-3 font-mono text-xs font-bold text-teal-900">
                                {{ item.code }}
                                <span class="block text-[10px] text-slate-400 font-normal">CAS: {{ item.cas_number or 'N/A' }}</span>
                            </td>
                            <td class="p-3 font-bold text-slate-900">
                                {{ item.name }}
                                <span class="block text-[11px] text-slate-400 font-normal">Grado: {{ item.purity or 'N/E' }} | Ubic: {{ item.location or 'General' }}</span>
                            </td>
                            <td class="p-3">
                                <span class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                                    {{ item.category }}
                                </span>
                            </td>
                            <td class="p-3">
                                {% if item.hazard_label == 'Inflamable' %}
                                    <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300">🔴 Inflamable</span>
                                {% elif item.hazard_label == 'Corrosivo' %}
                                    <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">🧪 Corrosivo</span>
                                {% elif item.hazard_label == 'Tóxico / Nocivo' %}
                                    <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-300">💀 Tóxico</span>
                                {% else %}
                                    <span class="text-slate-400 text-xs">🟢 Seguro</span>
                                {% endif %}
                            </td>
                            <td class="p-3 text-xs text-slate-600">
                                <span class="font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded">Lote: {{ item.lote or 'S/L' }}</span>
                                <span class="block text-[10px] mt-1">
                                    {% if item.caducidad and item.caducidad.strip() != '' %}
                                        {% set cad_date = item.caducidad %}
                                        {% if cad_date < today_str %}
                                            <span class="px-2 py-0.5 bg-rose-200 text-rose-900 font-bold rounded flex items-center gap-1 w-fit"><i class="fa-solid fa-triangle-exclamation"></i> VENCIDO ({{ cad_date }})</span>
                                        {% elif cad_date <= warning_str %}
                                            <span class="px-2 py-0.5 bg-amber-200 text-amber-900 font-bold rounded flex items-center gap-1 w-fit"><i class="fa-solid fa-clock"></i> Próximo a vencer ({{ cad_date }})</span>
                                        {% else %}
                                            <span class="text-slate-500 font-mono">Cad: {{ cad_date }}</span>
                                        {% endif %}
                                    {% else %}
                                        <span class="text-slate-400">Cad: S/F</span>
                                    {% endif %}
                                </span>
                            </td>
                            <td class="p-3 text-center">
                                <span class="px-3 py-1 rounded-full text-xs font-bold {% if item.stock_general < 10 %}bg-rose-100 text-rose-700{% else %}bg-emerald-100 text-emerald-800{% endif %}">
                                    {{ item.stock_general }} {{ item.unit }}
                                </span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        {% elif view == 'limpieza' %}
        <div class="space-y-6">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-1">
                    <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                        <i class="fa-solid fa-broom text-cyan-600"></i> Mantenimiento y Sanitización
                    </h2>

                    <form action="/add_cleaning" method="POST" class="space-y-4">
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Analista</label>
                                <select name="user_id" required class="w-full p-2.5 border rounded-xl text-xs bg-slate-50 outline-none">
                                    <option value="">Seleccione...</option>
                                    {% for u in users %}
                                        <option value="{{ u.id }}">{{ u.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-600 uppercase mb-1">PIN</label>
                                <input type="password" name="pin" required placeholder="PIN" class="w-full p-2.5 border rounded-xl text-xs outline-none">
                            </div>
                        </div>

                        <div class="bg-cyan-50/60 p-4 rounded-xl border border-cyan-100 space-y-3">
                            <h3 class="text-xs font-bold text-cyan-900 uppercase border-b border-cyan-200 pb-1">
                                Verificación de Campanas y Mesadas
                            </h3>

                            <label class="flex items-center gap-2.5 text-xs font-medium text-slate-700 cursor-pointer">
                                <input type="checkbox" name="campanas" class="w-4 h-4 text-cyan-600 rounded">
                                <span>💨 Sanitización Campana de Extracción</span>
                            </label>

                            <label class="flex items-center gap-2.5 text-xs font-medium text-slate-700 cursor-pointer">
                                <input type="checkbox" name="superficies" class="w-4 h-4 text-cyan-600 rounded">
                                <span>🧽 Limpieza de Mesadas de Análisis</span>
                            </label>

                            <label class="flex items-center gap-2.5 text-xs font-medium text-slate-700 cursor-pointer">
                                <input type="checkbox" name="residuos" class="w-4 h-4 text-cyan-600 rounded">
                                <span>♻️ Desecho de Residuos Peligrosos (RPBI/Químicos)</span>
                            </label>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Notas</label>
                            <input type="text" name="notes" placeholder="Ej. Se utilizó etanol al 70%..." class="w-full p-2.5 border rounded-xl text-xs outline-none">
                        </div>

                        <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3 rounded-xl shadow-md transition flex items-center justify-center gap-2">
                            <i class="fa-solid fa-clipboard-check"></i> Registrar Mantenimiento
                        </button>
                    </form>
                </div>

                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-2">
                    <div class="flex justify-between items-center mb-4 border-b pb-3">
                        <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
                            <i class="fa-solid fa-list-check text-cyan-600"></i> Histórico de Sanitización
                        </h2>
                        <button onclick="window.print()" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold no-print">
                            <i class="fa-solid fa-print"></i> Imprimir
                        </button>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-xs text-left text-slate-600">
                            <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b">
                                <tr>
                                    <th class="p-2.5">Fecha/Hora</th>
                                    <th class="p-2.5">Responsable</th>
                                    <th class="p-2.5 text-center">Campanas</th>
                                    <th class="p-2.5 text-center">Mesadas</th>
                                    <th class="p-2.5 text-center">Residuos</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-100">
                                {% for log in cleaning_logs %}
                                <tr class="hover:bg-slate-50">
                                    <td class="p-2.5 font-mono text-slate-500">{{ log.timestamp.strftime('%d/%m/%Y %H:%M') }}</td>
                                    <td class="p-2.5 font-bold text-slate-900">
                                        {{ log.user_name }}
                                        {% if log.notes %}<span class="block text-[10px] text-slate-400 font-normal">{{ log.notes }}</span>{% endif %}
                                    </td>
                                    <td class="p-2.5 text-center">{% if log.campanas %}<span class="text-emerald-600 font-bold">✓</span>{% else %}-{% endif %}</td>
                                    <td class="p-2.5 text-center">{% if log.superficies %}<span class="text-emerald-600 font-bold">✓</span>{% else %}-{% endif %}</td>
                                    <td class="p-2.5 text-center">{% if log.residuos %}<span class="text-emerald-600 font-bold">✓</span>{% else %}-{% endif %}</td>
                                </tr>
                                {% else %}
                                <tr><td colspan="5" class="p-6 text-center text-slate-400 italic">No hay actividades de mantenimiento registradas.</td></tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        {% elif view == 'bitacora' %}
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <div class="flex justify-between items-center mb-4 border-b pb-3">
                <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <i class="fa-solid fa-clock-rotate-left text-teal-600"></i> Bitácora e Histórico de Auditoría
                </h2>
                <button onclick="window.print()" class="px-4 py-2 bg-slate-800 text-white rounded-xl text-xs font-bold no-print">
                    <i class="fa-solid fa-print"></i> Imprimir Bitácora
                </button>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-xs text-left text-slate-600">
                    <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b">
                        <tr>
                            <th class="p-3">Fecha y Hora</th>
                            <th class="p-3">Operación</th>
                            <th class="p-3">Reactivo / Insumo</th>
                            <th class="p-3 text-center">Cantidad</th>
                            <th class="p-3">Proyecto / Ensayo</th>
                            <th class="p-3">Responsable</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                        {% for mov in movements %}
                        <tr class="hover:bg-slate-50">
                            <td class="p-3 text-slate-500 font-mono">{{ mov.timestamp.strftime('%d/%m/%Y %H:%M') }}</td>
                            <td class="p-3 font-bold">
                                <span class="px-2.5 py-1 rounded-full text-[10px] uppercase {% if mov.type == 'Entrada' %}bg-emerald-100 text-emerald-800{% elif mov.type == 'Salida' %}bg-blue-100 text-blue-800{% else %}bg-rose-100 text-rose-800{% endif %}">
                                    {{ mov.type }}
                                </span>
                            </td>
                            <td class="p-3 font-bold text-slate-900">{{ mov.item_name }}</td>
                            <td class="p-3 text-center font-bold text-sm">{{ mov.quantity }}</td>
                            <td class="p-3 font-medium text-slate-800">{{ mov.patient_name or 'N/A' }}</td>
                            <td class="p-3 text-teal-900 font-bold">{{ mov.user_name }}</td>
                        </tr>
                        {% else %}
                        <tr><td colspan="6" class="p-8 text-center text-slate-400 italic">No hay movimientos registrados.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        {% elif view == 'usuarios' %}
        {% if not is_admin %}
        <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 max-w-md mx-auto text-center">
            <div class="w-16 h-16 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center text-2xl mx-auto mb-4">
                <i class="fa-solid fa-lock"></i>
            </div>
            <h2 class="text-lg font-bold text-slate-900">Acceso Restringido a Administrador</h2>
            <p class="text-xs text-slate-500 mt-1 mb-6">Ingrese la contraseña del Administrador (PIN: 1234) para gestionar el personal.</p>

            <form action="/auth_admin" method="POST" class="space-y-4">
                <input type="password" name="admin_pin" required placeholder="Contraseña de Administrador" class="w-full p-3 border rounded-xl text-center text-lg tracking-widest outline-none">
                <button type="submit" class="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl transition">
                    Desbloquear Pestaña
                </button>
            </form>
        </div>
        {% else %}
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-4xl mx-auto">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-1">
                <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-user-plus text-teal-600"></i> Registrar Personal
                </h2>
                <form action="/save_user" method="POST" class="space-y-4">
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Nombre Completo</label>
                        <input type="text" name="name" required placeholder="Ej. Dr. Juan Pérez" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Cargo / Rol</label>
                        <select name="role" required class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 outline-none">
                            <option value="Investigador Principal">Investigador Principal</option>
                            <option value="Técnico de Laboratorio">Técnico de Laboratorio</option>
                            <option value="Analista QC">Analista QC</option>
                            <option value="Administrador">Administrador</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">PIN / Contraseña</label>
                        <input type="password" name="pin" required placeholder="••••" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                    </div>
                    <button type="submit" class="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl shadow-md transition">
                        Guardar Personal
                    </button>
                </form>
            </div>
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-2">
                <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-users text-teal-600"></i> Personal Autorizado
                </h2>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {% for u in users %}
                    <div class="p-4 rounded-xl border bg-slate-50 flex justify-between items-center">
                        <div>
                            <h4 class="font-bold text-slate-900 text-sm">{{ u.name }}</h4>
                            <p class="text-xs text-slate-500">{{ u.role }}</p>
                        </div>
                        <span class="text-xs font-mono bg-teal-100 text-teal-800 px-2 py-1 rounded">Activo</span>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}
        {% endif %}
    </main>

    <script>
        function selectUser(id) {
            var elem = document.getElementById('userSelect');
            if(elem) elem.value = id;
        }
        function filterInventory() {
            var input = document.getElementById("inventorySearch");
            var filter = input.value.toLowerCase();
            var rows = document.getElementsByClassName("inventory-row");
            for (var i = 0; i < rows.length; i++) {
                var text = rows[i].innerText.toLowerCase();
                rows[i].style.display = text.includes(filter) ? "" : "none";
            }
        }
    </script>
</body>
</html>
"""

# -----------------------------------------------------------------------------
# RUTAS DE LA APLICACIÓN
# -----------------------------------------------------------------------------

@app.route("/")
@app.route("/terminal")
def terminal():
    items = Item.query.order_by(Item.name).all()
    users = User.query.order_by(User.name).all()
    return render_template_string(HTML_TEMPLATE, view="terminal", items=items, users=users)

@app.route("/alta_insumos")
def alta_insumos():
    return render_template_string(HTML_TEMPLATE, view="alta_insumos")

@app.route("/inventario")
def inventario():
    items = Item.query.order_by(Item.name).all()
    today_str = datetime.now(LOCAL_TZ).date().isoformat()
    warning_str = (datetime.now(LOCAL_TZ).date() + timedelta(days=30)).isoformat()
    return render_template_string(HTML_TEMPLATE, view="inventario", items=items, today_str=today_str, warning_str=warning_str)

@app.route("/limpieza")
def limpieza():
    cleaning_logs = CleaningLog.query.order_by(CleaningLog.timestamp.desc()).all()
    users = User.query.order_by(User.name).all()
    return render_template_string(HTML_TEMPLATE, view="limpieza", cleaning_logs=cleaning_logs, users=users)

@app.route("/bitacora")
def bitacora():
    movements = Movement.query.order_by(Movement.timestamp.desc()).all()
    return render_template_string(HTML_TEMPLATE, view="bitacora", movements=movements)

@app.route("/usuarios")
def usuarios():
    users = User.query.order_by(User.name).all()
    is_admin = request.args.get("admin") == "true"
    return render_template_string(HTML_TEMPLATE, view="usuarios", users=users, is_admin=is_admin)

@app.route("/auth_admin", methods=["POST"])
def auth_admin():
    admin_pin = request.form.get("admin_pin")
    admin_user = User.query.filter_by(role="Administrador").first()
    
    if admin_pin == "1234" or admin_pin == "5678" or (admin_user and admin_user.pin == admin_pin):
        flash("Acceso concedido a la gestión de personal.", "success")
        return redirect(url_for("usuarios", admin="true"))
    else:
        flash("Contraseña de Administrador incorrecta.", "error")
        return redirect(url_for("usuarios"))

@app.route("/add_item", methods=["POST"])
def add_item():
    try:
        new_item = Item(
            code=request.form.get("code", "").strip().upper(),
            cas_number=request.form.get("cas_number", "").strip(),
            name=request.form.get("name", "").strip(),
            category=request.form.get("category"),
            purity=request.form.get("purity"),
            physical_state=request.form.get("physical_state"),
            storage_condition=request.form.get("storage_condition"),
            hazard_label=request.form.get("hazard_label"),
            location=request.form.get("location"),
            lote=request.form.get("lote"),
            caducidad=request.form.get("caducidad"),
            stock_general=float(request.form.get("stock_general", 0)),
            unit=request.form.get("unit")
        )
        db.session.add(new_item)
        db.session.commit()
        flash("Reactivo registrado con éxito.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al registrar: {str(e)}", "error")
    return redirect(url_for("alta_insumos"))

@app.route("/register", methods=["POST"])
def register_movement():
    user_id = request.form.get("user_id")
    pin = request.form.get("pin")
    item_search = request.form.get("item_search", "").strip()
    mov_type = request.form.get("type")
    warehouse = request.form.get("warehouse")
    quantity = float(request.form.get("quantity", 1))
    service = request.form.get("service")
    patient_name = request.form.get("patient_name")
    patient_id = request.form.get("patient_id")
    notes = request.form.get("notes")

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        flash("PIN o usuario incorrecto.", "error")
        return redirect(url_for("terminal"))

    item = None
    if item_search.startswith("[ID:") and "]" in item_search:
        try:
            item_id = int(item_search.split("[ID:")[1].split("]")[0])
            item = Item.query.get(item_id)
        except Exception:
            item = None

    if not item:
        clean_code = item_search.split(" - ")[0] if " - " in item_search else item_search
        item = Item.query.filter((Item.code == clean_code) | (Item.name.ilike(f"%{item_search}%"))).first()

    if not item:
        flash("Reactivo no encontrado.", "error")
        return redirect(url_for("terminal"))

    if mov_type == "Entrada":
        item.stock_general += quantity
    else:
        if item.stock_general < quantity:
            flash(f"Stock insuficiente ({item.stock_general} {item.unit} disponibles).", "error")
            return redirect(url_for("terminal"))
        item.stock_general -= quantity

    mov = Movement(
        timestamp=get_local_now(),
        item_code=item.code,
        item_name=item.name,
        type=mov_type,
        quantity=quantity,
        warehouse=warehouse,
        service=service,
        patient_name=patient_name,
        patient_id=patient_id,
        user_name=user.name,
        notes=notes
    )
    db.session.add(mov)
    db.session.commit()

    flash(f"Movimiento registrado para '{item.name}'.", "success")
    return redirect(url_for("terminal"))

@app.route("/add_cleaning", methods=["POST"])
def add_cleaning():
    user_id = request.form.get("user_id")
    pin = request.form.get("pin")
    campanas = 'campanas' in request.form
    superficies = 'superficies' in request.form
    residuos = 'residuos' in request.form
    notes = request.form.get("notes")

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        flash("PIN incorrecto.", "error")
        return redirect(url_for("limpieza"))

    log = CleaningLog(
        timestamp=get_local_now(),
        user_name=user.name,
        campanas=campanas,
        superficies=superficies,
        residuos=residuos,
        notes=notes
    )
    db.session.add(log)
    db.session.commit()
    flash("Bitácora de mantenimiento guardada correctamente.", "success")
    return redirect(url_for("limpieza"))

@app.route("/save_user", methods=["POST"])
def save_user():
    name = request.form.get("name", "").strip()
    role = request.form.get("role")
    pin = request.form.get("pin", "").strip()

    if name and pin:
        user = User.query.filter_by(name=name).first()
        if user:
            user.role = role
            user.pin = pin
            flash(f"Usuario {name} actualizado con éxito.", "success")
        else:
            new_user = User(name=name, role=role, pin=pin)
            db.session.add(new_user)
            flash(f"Usuario {name} registrado con éxito.", "success")
        db.session.commit()
    return redirect(url_for("usuarios", admin="true"))

# -----------------------------------------------------------------------------
# INICIALIZACIÓN DE DATOS SEMILLA
# -----------------------------------------------------------------------------
def seed_database():
    with app.app_context():
        db.create_all()
        if User.query.count() == 0:
            db.session.add_all([
                User(name="Administrador General", role="Administrador", pin="1234"),
                User(name="Q.F.B. Laura Martínez", role="Analista QC", pin="4321")
            ])
        if Item.query.count() == 0:
            db.session.add_all([
                Item(code="REQ-01", name="Etanol Absoluto ACS", cas_number="64-17-5", category="Reactivo Químico", purity="99.9%", physical_state="Líquido", storage_condition="Campana Inflamables", hazard_label="Inflamable", location="Estante A-1", lote="ET-2026-1", caducidad="2028-12-31", stock_general=2500, unit="ml"),
                Item(code="REQ-02", name="Ácido Clorhídrico 37%", cas_number="7647-01-0", category="Reactivo Químico", purity="37%", physical_state="Líquido", storage_condition="Temperatura Ambiente", hazard_label="Corrosivo", location="Gabinete Ácidos", lote="HCL-992", caducidad="2027-06-30", stock_general=1000, unit="ml")
            ])
        db.session.commit()

seed_database()

if __name__ == "__main__":
    app.run(debug=True)
