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

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)

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
    stock_almacen2 = db.Column(db.Float, default=0.0)
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

class ControlledLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_local_now)
    item_name = db.Column(db.String(150), nullable=False)
    patient_name = db.Column(db.String(150), nullable=False) # Proyecto / Autorización
    prescription_num = db.Column(db.String(50), nullable=False) # Folio COFEPRIS / Acta
    quantity = db.Column(db.Float, nullable=False)
    doctor_name = db.Column(db.String(150), nullable=True) # Analista / Químico Responsable
    user_name = db.Column(db.String(100), nullable=False)

class CleaningLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_local_now)
    user_name = db.Column(db.String(100), nullable=False)
    campanas = db.Column(db.Boolean, default=False)
    superficies = db.Column(db.Boolean, default=False)
    residuos = db.Column(db.Boolean, default=False)
    carton = db.Column(db.Boolean, default=False)
    equipo = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(250), nullable=True)

# -----------------------------------------------------------------------------
# PLANTILLA HTML INTEGRADA CON NUEVO DISEÑO CONCEPTUAL
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
                <a href="/terminal" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'terminal' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-pen-to-square"></i> Consumo / Ensayos
                </a>
                <a href="/alta_insumos" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'alta_insumos' %}bg-emerald-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-emerald-100{% endif %}">
                    <i class="fa-solid fa-plus-circle"></i> Alta Reactivo
                </a>
                <a href="/inventario" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'inventario' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-boxes-stacked"></i> Inventario
                </a>
                <a href="/controlados" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'controlados' %}bg-rose-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-rose-100{% endif %}">
                    <i class="fa-solid fa-radiation"></i> Precursores/Regulados
                </a>
                <a href="/limpieza" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'limpieza' %}bg-cyan-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-cyan-100{% endif %}">
                    <i class="fa-solid fa-broom"></i> Bitácora Área
                </a>
                <a href="/bitacora" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'bitacora' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-clock-rotate-left"></i> Historial
                </a>
                <a href="/usuarios" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'usuarios' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
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
                                <option value="Precursor Regulado">Precursor Regulado</option>
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
                            <option value="Precursor Regulado">🟣 Precursor Regulado (COFEPRIS)</option>
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
                                {% elif item.hazard_label == 'Precursor Regulado' %}
                                    <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-800 border border-indigo-300">🟣 Precursor</span>
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

        {% elif view == 'controlados' %}
        <div class="space-y-6">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-1">
                    <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                        <i class="fa-solid fa-radiation text-rose-600"></i> Consumo de Precursor / Regulado
                    </h2>

                    <form action="/add_controlled" method="POST" class="space-y-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Sustancia Regulada</label>
                            <input list="controlled_items_list" name="item_name" required placeholder="Seleccione precursor..." class="w-full p-2.5 border rounded-xl text-sm bg-rose-50 focus:bg-white focus:ring-2 focus:ring-rose-500 outline-none font-bold">
                            <datalist id="controlled_items_list">
                                {% for item in controlled_items %}
                                    <option value="{{ item.code }} - {{ item.name }} (Lote: {{ item.lote or 'S/L' }})">
                                {% endfor %}
                            </datalist>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-slate-6
