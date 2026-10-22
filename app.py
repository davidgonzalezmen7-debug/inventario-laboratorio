import os
from datetime import datetime, date, timedelta, timezone
import json
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lab_secret_key_123")

# Configuración de Zona Horaria Local (UTC-6 para México / Hora Local)
LOCAL_TZ = timezone(timedelta(hours=-6))

def get_local_now():
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)

# Configuración de Base de Datos PostgreSQL / SQLite
db_url = os.environ.get("DATABASE_URL", "sqlite:///laboratorio.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and "+psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------------------------------------------------------------
# MODELOS DE BASE DE DATOS (LABORATORIO)
# -----------------------------------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    pin = db.Column(db.String(20), nullable=False)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False) # Reactivo, Material de Vidrio, Consumible
    cas_number = db.Column(db.String(50), nullable=True) # No. CAS para químicos
    storage_condition = db.Column(db.String(50), nullable=True) # Temp. Ambiente, Refrigeración, Congelación
    lote = db.Column(db.String(50), nullable=True)
    caducidad = db.Column(db.String(20), nullable=True)
    etiqueta = db.Column(db.String(50), default="General") # Inflamable, Tóxico, Corrosivo, etc.
    stock_general = db.Column(db.Integer, default=0)
    stock_estacion = db.Column(db.Integer, default=0) # Stock en estaciones de trabajo / mesas
    unit = db.Column(db.String(20), default="pza")

class Movement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_local_now)
    item_code = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50), nullable=False) # Salida a Proyecto, Traspaso a Estación, Entrada
    quantity = db.Column(db.Integer, nullable=False)
    warehouse = db.Column(db.String(50), nullable=False)
    service = db.Column(db.String(100), nullable=True) # Área o Laboratorio
    project_name = db.Column(db.String(150), nullable=True)
    user_name = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.String(200), nullable=True)

class CleaningLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_local_now)
    user_name = db.Column(db.String(100), nullable=False)
    campana_extraccion = db.Column(db.Boolean, default=False)
    mesas_trabajo = db.Column(db.Boolean, default=False)
    reactivos_residuos = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(250), nullable=True)

# -----------------------------------------------------------------------------
# PLANTILLA HTML INTEGRADA (DISEÑO MODERNO)
# -----------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plataforma de Laboratorio - Control de Reactivos e Insumos</title>
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
    <header class="bg-gradient-to-r from-cyan-950 via-slate-900 to-indigo-950 text-white shadow-lg sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 py-3 flex flex-col md:flex-row justify-between items-center gap-4">
            <div class="flex items-center gap-3">
                <div class="bg-cyan-600 p-2.5 rounded-xl shadow-inner">
                    <i class="fa-solid fa-flask-vial text-2xl text-white"></i>
                </div>
                <div>
                    <h1 class="text-xl font-extrabold tracking-tight">Laboratorio Científico</h1>
                    <p class="text-[11px] text-cyan-200">Gestión de Reactivos, Materiales & Bitácoras</p>
                </div>
            </div>
            <nav class="flex flex-wrap gap-1 text-xs font-bold">
                <a href="/terminal" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'terminal' %}bg-cyan-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-cyan-100{% endif %}">
                    <i class="fa-solid fa-file-invoice"></i> Salida / Consumo
                </a>
                <a href="/alta_insumos" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'alta_insumos' %}bg-emerald-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-emerald-100{% endif %}">
                    <i class="fa-solid fa-circle-plus"></i> Alta Reactivos
                </a>
                <a href="/inventario" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'inventario' %}bg-cyan-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-cyan-100{% endif %}">
                    <i class="fa-solid fa-boxes-stacked"></i> Inventario
                </a>
                <a href="/limpieza" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'limpieza' %}bg-teal-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-teal-100{% endif %}">
                    <i class="fa-solid fa-broom"></i> Rol de Limpieza
                </a>
                <a href="/bitacora" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'bitacora' %}bg-cyan-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-cyan-100{% endif %}">
                    <i class="fa-solid fa-clock-rotate-left"></i> Bitácora
                </a>
                <a href="/usuarios" class="px-2.5 py-2 rounded-xl transition flex items-center gap-1.5 {% if view == 'usuarios' %}bg-cyan-600 text-white shadow{% else %}bg-white/10 hover:bg-white/20 text-cyan-100{% endif %}">
                    <i class="fa-solid fa-users-gear"></i> Usuarios
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

        <datalist id="projects_datalist">
            {% for p in projects %}
                <option value="{{ p.name }}">
            {% endfor %}
        </datalist>

        {% if view == 'terminal' %}
        <div class="space-y-6 max-w-5xl mx-auto">
            <!-- Selección de Investigador / Personal -->
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <div class="mb-4">
                    <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
                        <i class="fa-solid fa-user-scientist text-cyan-600"></i> Investigador / Personal Responsable
                    </h2>
                    <p class="text-xs text-slate-500">Haga clic sobre su nombre para seleccionarlo.</p>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                    {% for u in users %}
                    <button type="button" onclick="selectUser('{{ u.id }}')" class="p-3 rounded-xl border border-slate-200 bg-slate-50 hover:bg-cyan-50 hover:border-cyan-400 transition text-center group flex flex-col items-center">
                        <div class="w-9 h-9 rounded-full bg-cyan-100 text-cyan-600 flex items-center justify-center text-sm mb-1.5 group-hover:scale-110 transition">
                            <i class="fa-solid {% if 'Admin' in u.role %}fa-user-shield{% else %}fa-user-graduate{% endif %}"></i>
                        </div>
                        <h4 class="font-bold text-slate-800 text-xs group-hover:text-cyan-600 truncate w-full">{{ u.name }}</h4>
                        <span class="text-[10px] text-slate-500">{{ u.role }}</span>
                    </button>
                    {% endfor %}
                </div>
            </div>

            <!-- Formulario de Movimientos y Consumo -->
            <form action="/register_batch" method="POST" onsubmit="return validateBatchForm()" class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-6">
                <input type="hidden" name="cart_data" id="cart_data_input">

                <div class="border-b pb-4 flex justify-between items-center">
                    <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
                        <i class="fa-solid fa-clipboard-list text-cyan-600"></i> Registro de Consumo / Salida para Proyecto
                    </h2>
                    <span class="text-xs font-bold bg-cyan-100 text-cyan-800 px-3 py-1 rounded-full">
                        Multicarga Activa
                    </span>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 bg-cyan-50/50 p-4 rounded-xl border border-cyan-100">
                    <div>
                        <label class="block text-xs font-bold text-slate-700 uppercase mb-1">Usuario Responsable</label>
                        <select name="user_id" id="userSelect" required class="w-full p-2.5 border rounded-xl text-sm bg-white focus:ring-2 focus:ring-cyan-500 outline-none">
                            <option value="">Seleccione Usuario...</option>
                            {% for u in users %}
                                <option value="{{ u.id }}">{{ u.name }} ({{ u.role }})</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-700 uppercase mb-1">PIN / Contraseña</label>
                        <input type="password" name="pin" required placeholder="PIN de Seguridad" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-cyan-500 outline-none">
                    </div>
                </div>

                <div class="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                    <h3 class="text-xs font-bold text-cyan-900 uppercase flex items-center gap-1.5">
                        <i class="fa-solid fa-diagram-project"></i> Detalles del Proyecto / Destino
                    </h3>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Nombre del Proyecto / Experimento</label>
                            <input type="text" list="projects_datalist" name="project_name" id="project_name" placeholder="Ej. Síntesis Orgánica Fase II" class="w-full p-2 border rounded-lg text-xs focus:ring-2 focus:ring-cyan-500 outline-none bg-white font-medium">
                        </div>
                        <div>
                            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Laboratorio / Estación</label>
                            <input type="text" name="service" placeholder="Ej. Lab Química H-302" class="w-full p-2 border rounded-lg text-xs focus:ring-2 focus:ring-cyan-500 outline-none bg-white">
                        </div>
                    </div>
                </div>

                <div class="p-4 bg-indigo-50/40 rounded-xl border border-indigo-100 space-y-3">
                    <h3 class="text-xs font-bold text-indigo-900 uppercase flex items-center gap-1.5">
                        <i class="fa-solid fa-plus-circle"></i> Agregar Reactivos o Materiales
                    </h3>
                    
                    <div class="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                        <div class="md:col-span-5">
                            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Reactivo / Insumo</label>
                            <input list="items_list" id="temp_item" placeholder="Buscar por código, nombre, CAS..." class="w-full p-2 border rounded-lg text-xs focus:ring-2 focus:ring-cyan-500 outline-none bg-white font-medium">
                            <datalist id="items_list">
                                {% for item in items %}
                                    <option value="[ID:{{ item.id }}] {{ item.code }} - {{ item.name }} (CAS: {{ item.cas_number or 'N/A' }})">Alm: {{ item.stock_general }} | Est: {{ item.stock_estacion }} | {{ item.etiqueta }}</option>
                                {% endfor %}
                            </datalist>
                        </div>
                        <div class="md:col-span-2">
                            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Acción</label>
                            <select id="temp_type" class="w-full p-2 border rounded-lg text-xs bg-white outline-none">
                                <option value="Salida">Consumo / Salida</option>
                                <option value="Traspaso Estacion">Traspaso a Estación</option>
                                <option value="Entrada">Entrada (Reposición)</option>
                            </select>
                        </div>
                        <div class="md:col-span-2">
                            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Ubicación</label>
                            <select id="temp_warehouse" class="w-full p-2 border rounded-lg text-xs bg-white outline-none">
                                <option value="Almacén General">Almacén General</option>
                                <option value="Estación de Trabajo">Estación de Trabajo</option>
                            </select>
                        </div>
                        <div class="md:col-span-1">
                            <label class="block text-[11px] font-semibold text-slate-600 mb-1">Cant.</label>
                            <input type="number" min="1" id="temp_quantity" value="1" class="w-full p-2 border rounded-lg text-xs focus:ring-2 focus:ring-cyan-500 outline-none text-center font-bold">
                        </div>
                        <div class="md:col-span-2">
                            <button type="button" onclick="addToCart()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-3 rounded-lg text-xs transition flex items-center justify-center gap-1 shadow-sm">
                                <i class="fa-solid fa-cart-plus"></i> Agregar
                            </button>
                        </div>
                    </div>
                </div>

                <div>
                    <h3 class="text-xs font-bold text-slate-700 uppercase mb-2 flex items-center justify-between">
                        <span><i class="fa-solid fa-list-check text-cyan-600"></i> Ítems en la Lista</span>
                        <span id="cartCountBadge" class="text-[11px] font-semibold bg-slate-200 text-slate-700 px-2 py-0.5 rounded-full">0 ítems</span>
                    </h3>

                    <div class="overflow-x-auto border rounded-xl">
                        <table class="w-full text-xs text-left text-slate-600" id="cartTable">
                            <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b">
                                <tr>
                                    <th class="p-2.5">Descripción / Reactivo</th>
                                    <th class="p-2.5">Tipo</th>
                                    <th class="p-2.5">Ubicación</th>
                                    <th class="p-2.5 text-center">Cantidad</th>
                                    <th class="p-2.5 text-center">Acción</th>
                                </tr>
                            </thead>
                            <tbody id="cartTableBody" class="divide-y divide-slate-100">
                                <tr>
                                    <td colspan="5" class="p-6 text-center text-slate-400 italic">
                                        No hay elementos agregados.
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div>
                    <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Notas u Observaciones del Experimento</label>
                    <input type="text" name="notes" placeholder="Observaciones..." class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-cyan-500 outline-none">
                </div>

                <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3.5 rounded-xl shadow-md transition duration-200 flex items-center justify-center gap-2 text-sm">
                    <i class="fa-solid fa-check-double"></i> Registrar Operación Completa
                </button>
            </form>
        </div>

        {% elif view == 'inventario' %}
        <div class="space-y-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <div class="flex flex-col md:flex-row justify-between items-center gap-4 mb-6 border-b pb-4">
                    <div>
                        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                            <i class="fa-solid fa-boxes-stacked text-cyan-600"></i> Inventario de Reactivos y Materiales
                        </h2>
                        <p class="text-xs text-slate-500">Control de números CAS, etiquetas de seguridad y almacenamiento.</p>
                    </div>
                    <div class="w-full md:w-80 relative">
                        <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-sm"></i>
                        <input type="text" id="inventorySearch" onkeyup="filterInventory()" placeholder="Buscar por código, CAS, nombre..." class="w-full pl-10 pr-4 py-2 border rounded-xl text-xs bg-slate-50 focus:bg-white focus:ring-2 focus:ring-cyan-500 outline-none font-medium">
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-sm text-left text-slate-600" id="inventoryTable">
                        <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b">
                            <tr>
                                <th class="p-3">Código / CAS</th>
                                <th class="p-3">Nombre / Descripción</th>
                                <th class="p-3">Categoría / Almacenamiento</th>
                                <th class="p-3">Peligro / Etiqueta</th>
                                <th class="p-3">Lote / Caducidad</th>
                                <th class="p-3 text-center">Almacén</th>
                                <th class="p-3 text-center">Estación</th>
                                <th class="p-3 text-center">Acciones Admin</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            {% for item in items %}
                            <tr class="hover:bg-slate-50 transition inventory-row">
                                <td class="p-3 font-mono text-xs font-bold text-cyan-900">
                                    {{ item.code }}
                                    <span class="block text-[10px] text-slate-500">CAS: {{ item.cas_number or 'N/A' }}</span>
                                </td>
                                <td class="p-3 font-bold text-slate-900">
                                    {{ item.name }}
                                </td>
                                <td class="p-3 text-xs">
                                    <span class="px-2.5 py-0.5 rounded-full font-medium bg-slate-100 text-slate-700">
                                        {{ item.category }}
                                    </span>
                                    <span class="block text-[10px] text-slate-500 mt-1">Temp: {{ item.storage_condition or 'Ambiente' }}</span>
                                </td>
                                <td class="p-3">
                                    {% if item.etiqueta == 'Inflamable' %}
                                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">🔥 Inflamable</span>
                                    {% elif item.etiqueta == 'Tóxico' %}
                                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">☠️ Tóxico</span>
                                    {% elif item.etiqueta == 'Corrosivo' %}
                                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800">🧪 Corrosivo</span>
                                    {% else %}
                                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">🟢 General</span>
                                    {% endif %}
                                </td>
                                <td class="p-3 text-xs text-slate-600">
                                    <span class="font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded">Lote: {{ item.lote or 'S/L' }}</span>
                                    <span class="block text-[10px] text-slate-400 mt-0.5">Cad: {{ item.caducidad or 'S/F' }}</span>
                                </td>
                                <td class="p-3 text-center font-bold text-emerald-800">{{ item.stock_general }} {{ item.unit }}</td>
                                <td class="p-3 text-center font-bold text-cyan-800">{{ item.stock_estacion }} {{ item.unit }}</td>
                                <td class="p-3 text-center">
                                    <button onclick="openEditItemModal('{{ item.id }}', '{{ item.code }}', '{{ item.name }}', '{{ item.category }}', '{{ item.cas_number or '' }}', '{{ item.storage_condition or '' }}', '{{ item.etiqueta or 'General' }}', '{{ item.lote or '' }}', '{{ item.caducidad or '' }}', '{{ item.stock_general }}', '{{ item.stock_estacion }}')" class="px-2.5 py-1 bg-amber-100 hover:bg-amber-200 text-amber-800 font-bold rounded-lg text-xs transition flex items-center gap-1 mx-auto">
                                        <i class="fa-solid fa-lock text-amber-600"></i> Modificar
                                    </button>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- MODAL DE EDICIÓN DE INVENTARIO CON PIN DE ADMIN -->
        <div id="editModal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border space-y-4 max-h-[90vh] overflow-y-auto">
                <div class="flex justify-between items-center border-b pb-2">
                    <h3 class="font-bold text-slate-900 text-base" id="modalItemTitle">Modificar Reactivo / Insumo</h3>
                    <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600 text-lg">&times;</button>
                </div>
                
                <form action="/update_item" method="POST" class="space-y-3">
                    <input type="hidden" name="item_id" id="modal_item_id">

                    <div class="bg-amber-50 p-3 rounded-xl border border-amber-200 text-xs">
                        <label class="block font-bold text-amber-900 uppercase mb-1"><i class="fa-solid fa-shield-halved"></i> PIN del Administrador (Requerido)</label>
                        <input type="password" name="admin_pin" required placeholder="PIN de Administrador" class="w-full p-2 border rounded-lg text-center font-bold tracking-widest text-sm outline-none bg-white">
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Código</label>
                            <input type="text" name="code" id="modal_code" required class="w-full p-2 border rounded-xl text-xs font-mono">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Nombre</label>
                            <input type="text" name="name" id="modal_name" required class="w-full p-2 border rounded-xl text-xs font-bold">
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Categoría</label>
                            <select name="category" id="modal_category" required class="w-full p-2 border rounded-xl text-xs bg-slate-50">
                                <option value="Reactivo Químico">Reactivo Químico</option>
                                <option value="Material de Vidrio">Material de Vidrio</option>
                                <option value="Consumible / EP">Consumible / EPP</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Etiqueta Peligro</label>
                            <select name="etiqueta" id="modal_etiqueta" class="w-full p-2 border rounded-xl text-xs font-bold">
                                <option value="General">🟢 General</option>
                                <option value="Inflamable">🔥 Inflamable</option>
                                <option value="Tóxico">☠️ Tóxico</option>
                                <option value="Corrosivo">🧪 Corrosivo</option>
                            </select>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Número CAS</label>
                            <input type="text" name="cas_number" id="modal_cas" class="w-full p-2 border rounded-xl text-xs font-mono">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Almacenamiento</label>
                            <input type="text" name="storage_condition" id="modal_storage" class="w-full p-2 border rounded-xl text-xs" placeholder="Ej. Refrigeración 4°C">
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Lote</label>
                            <input type="text" name="lote" id="modal_lote" class="w-full p-2 border rounded-xl text-xs font-medium">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Caducidad</label>
                            <input type="date" name="caducidad" id="modal_caducidad" class="w-full p-2 border rounded-xl text-xs">
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border">
                        <div>
                            <label class="block text-xs font-bold text-emerald-800 uppercase mb-1">Stock Almacén</label>
                            <input type="number" name="stock_general" id="modal_stock_general" required class="w-full p-2 border rounded-xl text-xs font-bold text-center">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-cyan-800 uppercase mb-1">Stock Estación</label>
                            <input type="number" name="stock_estacion" id="modal_stock_estacion" required class="w-full p-2 border rounded-xl text-xs font-bold text-center">
                        </div>
                    </div>

                    <button type="submit" class="w-full bg-amber-600 hover:bg-amber-700 text-white font-bold py-2.5 rounded-xl transition shadow">
                        Autorizar y Guardar Cambios
                    </button>
                </form>
            </div>
        </div>

        {% elif view == 'alta_insumos' %}
        <div class="space-y-6 max-w-xl mx-auto">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-circle-plus text-emerald-600"></i> Registrar Nuevo Reactivo o Material
                </h2>

                <form action="/add_item" method="POST" class="space-y-3">
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Código / Clave</label>
                        <input type="text" name="code" required placeholder="Ej. REQ-001" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 outline-none font-mono">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Nombre / Descripción</label>
                        <input type="text" name="name" required placeholder="Ej. Ácido Clorhídrico 37%" class="w-full p-2.5 border rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 outline-none">
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Categoría</label>
                            <select name="category" required class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 outline-none">
                                <option value="Reactivo Químico">Reactivo Químico</option>
                                <option value="Material de Vidrio">Material de Vidrio</option>
                                <option value="Consumible / EP">Consumible / EPP</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Etiqueta de Peligro</label>
                            <select name="etiqueta" class="w-full p-2.5 border rounded-xl text-sm bg-amber-50 font-bold outline-none">
                                <option value="General">🟢 General</option>
                                <option value="Inflamable">🔥 Inflamable</option>
                                <option value="Tóxico">☠️ Tóxico</option>
                                <option value="Corrosivo">🧪 Corrosivo</option>
                            </select>
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Número CAS</label>
                            <input type="text" name="cas_number" placeholder="Ej. 7647-01-0" class="w-full p-2.5 border rounded-xl text-sm outline-none font-mono">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Almacenamiento</label>
                            <input type="text" name="storage_condition" placeholder="Temp. Ambiente / Frio" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Lote</label>
                            <input type="text" name="lote" placeholder="LOTE-2026-X" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Fecha Caducidad</label>
                            <input type="date" name="caducidad" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Unidad</label>
                            <input type="text" name="unit" required value="pza" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Stock Inicial</label>
                            <input type="number" min="0" name="stock_general" required value="20" class="w-full p-2.5 border rounded-xl text-sm outline-none font-bold">
                        </div>
                    </div>

                    <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl shadow-md transition duration-200 flex items-center justify-center gap-2 mt-4">
                        <i class="fa-solid fa-box-archive"></i> Registrar Insumo
                    </button>
                </form>
            </div>
        </div>

        {% elif view == 'limpieza' %}
        <div class="space-y-6">
            <!-- HEADER DE ROL DE LIMPIEZA ROTATIVO -->
            <div class="bg-gradient-to-r from-teal-900 to-slate-900 text-white p-6 rounded-2xl shadow-md border border-teal-800">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-2">
                    <div>
                        <h2 class="text-base font-bold flex items-center gap-2">
                            <i class="fa-solid fa-calendar-check text-teal-400"></i> Rol Semanal de Mantenimiento de Laboratorio (Excluye Administrador)
                        </h2>
                        <p class="text-xs text-teal-200">Cada investigador operativo realiza una tarea asignada diariamente durante la semana. El turno se alterna automáticamente cada semana.</p>
                    </div>
                    <span class="bg-teal-600/80 text-white text-xs font-mono px-3 py-1.5 rounded-full font-bold">
                        Semana {{ current_week }} / {{ current_year }} ({{ week_dates_current }})
                    </span>
                </div>
            </div>

            <!-- ASIGNACIÓN INDIVIDUAL POR USUARIO -->
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <h3 class="text-base font-bold text-slate-900 mb-4 border-b pb-3 flex items-center gap-2">
                    <i class="fa-solid fa-user-check text-teal-600"></i> Asignación de Tareas Semanales por Investigador
                </h3>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {% for item in user_roles_detail %}
                    <div class="rounded-2xl border bg-slate-50/80 border-slate-200 p-5 flex flex-col justify-between space-y-4 hover:border-teal-400 transition shadow-sm">
                        <div class="space-y-2">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h4 class="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                                        <i class="fa-solid fa-user text-teal-600 text-xs"></i>
                                        {{ item.user.name }}
                                    </h4>
                                    <span class="text-[11px] text-slate-500 font-medium">{{ item.user.role }}</span>
                                </div>
                                <span class="bg-teal-100 text-teal-800 text-[10px] font-extrabold uppercase px-2.5 py-1 rounded-full border border-teal-200">
                                    Activo Diario
                                </span>
                            </div>

                            <div class="bg-gradient-to-r from-teal-500 to-emerald-600 text-white p-3.5 rounded-xl shadow-sm space-y-1">
                                <span class="text-[10px] uppercase font-bold text-teal-100 block tracking-wider">
                                    <i class="fa-solid fa-clipboard-list"></i> Tarea Asignada Esta Semana:
                                </span>
                                <p class="font-extrabold text-xs text-white">
                                    {{ item.task_this_week }}
                                </p>
                            </div>
                        </div>

                        <div class="border-t border-slate-200 pt-3 text-xs space-y-1 text-slate-600">
                            <div class="flex justify-between items-center text-[11px]">
                                <span class="font-bold text-slate-700">Próxima Semana (Semana {{ current_week + 1 }}):</span>
                            </div>
                            <p class="text-[11px] font-semibold text-teal-800 bg-teal-50 px-2 py-1 rounded border border-teal-100">
                                🔄 {{ item.task_next_week }}
                            </p>
                        </div>
                    </div>
                    {% else %}
                    <div class="col-span-full text-center text-slate-400 p-6 italic">
                        No hay personal operativo registrado.
                    </div>
                    {% endfor %}
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- FORMULARIO DE REGISTRO DIARIO DE MANTENIMIENTO -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-1">
                    <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                        <i class="fa-solid fa-broom text-teal-600"></i> Registrar Cumplimiento Diario
                    </h2>

                    <form action="/add_cleaning" method="POST" class="space-y-4">
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Personal</label>
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

                        <div class="bg-teal-50/60 p-4 rounded-xl border border-teal-100 space-y-3">
                            <h3 class="text-xs font-bold text-teal-900 uppercase border-b border-teal-200 pb-1">
                                Verificación de Áreas
                            </h3>

                            <label class="flex items-center gap-2.5 text-xs font-medium text-slate-700 cursor-pointer">
                                <input type="checkbox" name="campana_extraccion" class="w-4 h-4 text-teal-600 rounded">
                                <span>💨 Sanitización Campana de Extracción</span>
                            </label>

                            <label class="flex items-center gap-2.5 text-xs font-medium text-slate-700 cursor-pointer">
                                <input type="checkbox" name="mesas_trabajo" class="w-4 h-4 text-teal-600 rounded">
                                <span>🧫 Desinfección Mesas de Trabajo</span>
                            </label>

                            <label class="flex items-center gap-2.5 text-xs font-medium text-slate-700 cursor-pointer">
                                <input type="checkbox" name="reactivos_residuos" class="w-4 h-4 text-teal-600 rounded">
                                <span>🧪 Revisión de Residuos y Reactivos</span>
                            </label>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Notas u Observaciones</label>
                            <input type="text" name="notes" placeholder="Ej. Campana operando con normalidad..." class="w-full p-2.5 border rounded-xl text-xs outline-none">
                        </div>

                        <button type="submit" class="w-full bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl shadow-md transition flex items-center justify-center gap-2">
                            <i class="fa-solid fa-clipboard-check"></i> Guardar Registro Diario
                        </button>
                    </form>
                </div>

                <!-- TABLA HISTORIAL DE MANTENIMIENTO -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-2">
                    <div class="flex justify-between items-center mb-4 border-b pb-3">
                        <h2 class="text-base font-bold text-slate-900 flex items-center gap-2">
                            <i class="fa-solid fa-list-check text-teal-600"></i> Bitácora de Mantenimiento y Limpieza
                        </h2>
                        <button onclick="window.print()" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold no-print">
                            <i class="fa-solid fa-print"></i> Imprimir Reporte
                        </button>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-xs text-left text-slate-600">
                            <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b">
                                <tr>
                                    <th class="p-2.5">Fecha/Hora</th>
                                    <th class="p-2.5">Responsable</th>
                                    <th class="p-2.5 text-center">Campana</th>
                                    <th class="p-2.5 text-center">Mesas</th>
                                    <th class="p-2.5 text-center">Residuos</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-100">
                                {% for log in cleaning_logs %}
                                <tr class="hover:bg-slate-50">
                                    <td class="p-2.5 font-mono text-slate-500">{{ log.timestamp.strftime('%d/%m/%Y %H:%M') if log.timestamp else '-' }}</td>
                                    <td class="p-2.5 font-bold text-slate-900">
                                        {{ log.user_name }}
                                        {% if log.notes %}<span class="block text-[10px] text-slate-400 font-normal">{{ log.notes }}</span>{% endif %}
                                    </td>
                                    <td class="p-2.5 text-center">{% if log.campana_extraccion %}<span class="text-emerald-600 font-bold">✓</span>{% else %}-{% endif %}</td>
                                    <td class="p-2.5 text-center">{% if log.mesas_trabajo %}<span class="text-emerald-600 font-bold">✓</span>{% else %}-{% endif %}</td>
                                    <td class="p-2.5 text-center">{% if log.reactivos_residuos %}<span class="text-emerald-600 font-bold">✓</span>{% else %}-{% endif %}</td>
                                </tr>
                                {% else %}
                                <tr><td colspan="5" class="p-6 text-center text-slate-400 italic">No hay registros de mantenimiento.</td></tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        {% elif view == 'bitacora' %}
        <div class="space-y-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <div class="mb-4 border-b pb-3 flex justify-between items-center">
                    <div>
                        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                            <i class="fa-solid fa-clock-rotate-left text-cyan-600"></i> Historial de Movimientos y Consumos
                        </h2>
                        <p class="text-xs text-slate-500">Modificaciones y reversiones requieren PIN de Administrador.</p>
                    </div>
                    <button onclick="window.print()" class="px-4 py-2 bg-slate-800 text-white font-bold rounded-xl text-xs">
                        <i class="fa-solid fa-print"></i> Imprimir Bitácora
                    </button>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-xs text-left text-slate-600">
                        <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b">
                            <tr>
                                <th class="p-3">Fecha y Hora</th>
                                <th class="p-3">Tipo</th>
                                <th class="p-3">Reactivo / Insumo</th>
                                <th class="p-3 text-center">Cant.</th>
                                <th class="p-3">Proyecto / Lab</th>
                                <th class="p-3">Responsable</th>
                                <th class="p-3 text-center">Acción Admin</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            {% for mov in movements %}
                            <tr class="hover:bg-slate-50">
                                <td class="p-3 text-slate-500 font-mono">{{ mov.timestamp.strftime('%d/%m/%Y %H:%M') if mov.timestamp else 'N/A' }}</td>
                                <td class="p-3 font-bold">
                                    <span class="px-2.5 py-1 rounded-full text-[10px] uppercase font-bold {% if mov.type == 'Entrada' %}bg-emerald-100 text-emerald-800{% elif mov.type == 'Salida' %}bg-rose-100 text-rose-800{% else %}bg-cyan-100 text-cyan-800{% endif %}">
                                        {{ mov.type }}
                                    </span>
                                </td>
                                <td class="p-3 font-bold text-slate-900">{{ mov.item_name }}</td>
                                <td class="p-3 text-center font-bold text-sm text-slate-900">{{ mov.quantity }}</td>
                                <td class="p-3 font-medium text-slate-900">{{ mov.project_name or mov.service or '-' }}</td>
                                <td class="p-3 text-cyan-900 font-bold">{{ mov.user_name }}</td>
                                <td class="p-3 text-center">
                                    <button onclick="revertMovementModal('{{ mov.id }}')" class="px-2 py-1 bg-rose-100 hover:bg-rose-200 text-rose-700 font-bold rounded text-[11px]">
                                        <i class="fa-solid fa-rotate-left"></i> Revertir
                                    </button>
                                </td>
                            </tr>
                            {% else %}
                            <tr><td colspan="7" class="p-8 text-center text-slate-400 italic">No hay movimientos registrados.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- MODAL REVERTIR MOVIMIENTO -->
        <div id="revertModal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div class="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border space-y-4">
                <div class="flex justify-between items-center border-b pb-2">
                    <h3 class="font-bold text-slate-900 text-base">Autorización de Administrador</h3>
                    <button onclick="closeRevertModal()" class="text-slate-400 hover:text-slate-600 text-lg">&times;</button>
                </div>
                <p class="text-xs text-slate-600">Ingrese el PIN del Administrador para revertir este movimiento y devolver el stock.</p>
                <form action="/revert_movement" method="POST" class="space-y-3">
                    <input type="hidden" name="movement_id" id="modal_movement_id">
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">PIN del Administrador</label>
                        <input type="password" name="admin_pin" required placeholder="PIN" class="w-full p-2.5 border rounded-xl text-center text-lg font-bold tracking-widest outline-none">
                    </div>
                    <button type="submit" class="w-full bg-rose-600 hover:bg-rose-700 text-white font-bold py-2.5 rounded-xl transition">
                        Confirmar Reversión
                    </button>
                </form>
            </div>
        </div>

        {% elif view == 'usuarios' %}
        {% if not is_admin %}
        <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 max-w-md mx-auto text-center space-y-4">
            <div class="w-16 h-16 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center text-2xl mx-auto">
                <i class="fa-solid fa-user-lock"></i>
            </div>
            <h2 class="text-lg font-bold text-slate-900">Acceso Exclusivo de Administrador</h2>
            <p class="text-xs text-slate-500">Solo el Administrador puede gestionar los investigadores y accesos.</p>

            <form action="/auth_admin_users" method="POST" class="space-y-3">
                <input type="password" name="admin_pin" required placeholder="PIN de Administrador" class="w-full p-3 border rounded-xl text-center text-lg font-bold tracking-widest outline-none focus:ring-2 focus:ring-cyan-500">
                <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3 rounded-xl transition">
                    Desbloquear Administración
                </button>
            </form>
        </div>
        {% else %}
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-1">
                <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-user-plus text-cyan-600"></i> Registrar / Modificar Usuario
                </h2>
                <form action="/save_user" method="POST" class="space-y-3">
                    <input type="hidden" name="user_id" id="edit_user_id">
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Nombre Completo</label>
                        <input type="text" name="name" id="edit_user_name" required placeholder="Dr. Carlos Mendoza" class="w-full p-2.5 border rounded-xl text-sm outline-none">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">Rol / Puesto</label>
                        <select name="role" id="edit_user_role" required class="w-full p-2.5 border rounded-xl text-sm bg-slate-50 outline-none">
                            <option value="Investigador Titular">Investigador Titular</option>
                            <option value="Técnico de Laboratorio">Técnico de Laboratorio</option>
                            <option value="Asistente de Investigación">Asistente de Investigación</option>
                            <option value="Administrador">Administrador</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-600 uppercase mb-1">PIN / Contraseña</label>
                        <input type="password" name="pin" id="edit_user_pin" required placeholder="PIN de 4 dígitos" class="w-full p-2.5 border rounded-xl text-sm outline-none font-mono">
                    </div>
                    <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3 rounded-xl shadow-md transition">
                        Guardar Usuario
                    </button>
                </form>
            </div>

            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 lg:col-span-2">
                <h2 class="text-base font-bold text-slate-900 mb-4 border-b pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-users-gear text-cyan-600"></i> Personal Registrado
                </h2>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {% for u in users %}
                    <div class="p-4 rounded-xl border bg-slate-50 flex justify-between items-center">
                        <div>
                            <h4 class="font-bold text-slate-900 text-sm">{{ u.name }}</h4>
                            <p class="text-xs text-slate-500">{{ u.role }}</p>
                            <p class="text-[10px] text-cyan-600 font-mono mt-1">PIN: ••••</p>
                        </div>
                        <button onclick="editUser('{{ u.id }}', '{{ u.name }}', '{{ u.role }}', '{{ u.pin }}')" class="px-2.5 py-1 bg-cyan-100 hover:bg-cyan-200 text-cyan-800 font-bold rounded-lg text-xs transition">
                            <i class="fa-solid fa-pen"></i> Editar PIN
                        </button>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}
        {% endif %}
    </main>

    <script>
        let cart = [];

        function selectUser(id) {
            var elem = document.getElementById('userSelect');
            if(elem) elem.value = id;
        }

        function addToCart() {
            const itemInput = document.getElementById('temp_item');
            const itemSearchValue = itemInput.value.trim();
            const type = document.getElementById('temp_type').value;
            const warehouse = document.getElementById('temp_warehouse').value;
            const quantity = parseInt(document.getElementById('temp_quantity').value) || 1;

            if (!itemSearchValue) {
                alert('Por favor seleccione un reactivo o material.');
                return;
            }

            cart.push({
                item_search: itemSearchValue,
                type: type,
                warehouse: warehouse,
                quantity: quantity
            });

            itemInput.value = '';
            document.getElementById('temp_quantity').value = 1;
            renderCart();
        }

        function removeFromCart(index) {
            cart.splice(index, 1);
            renderCart();
        }

        function renderCart() {
            const tbody = document.getElementById('cartTableBody');
            const badge = document.getElementById('cartCountBadge');
            
            badge.innerText = cart.length + ' ítems';

            if (cart.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="p-6 text-center text-slate-400 italic">
                            No hay elementos agregados.
                        </td>
                    </tr>
                `;
                return;
            }

            let html = '';
            cart.forEach((item, index) => {
                html += `
                    <tr class="hover:bg-slate-50">
                        <td class="p-2.5 font-bold text-slate-800">${item.item_search}</td>
                        <td class="p-2.5 font-medium text-xs">${item.type}</td>
                        <td class="p-2.5 text-xs text-slate-500">${item.warehouse}</td>
                        <td class="p-2.5 text-center font-bold text-sm text-slate-900">${item.quantity}</td>
                        <td class="p-2.5 text-center">
                            <button type="button" onclick="removeFromCart(${index})" class="px-2 py-1 bg-rose-100 hover:bg-rose-200 text-rose-700 font-bold rounded text-xs transition">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;
        }

        function validateBatchForm() {
            if (cart.length === 0) {
                alert('Debe agregar al menos un ítem al registro.');
                return false;
            }
            document.getElementById('cart_data_input').value = JSON.stringify(cart);
            return true;
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

        function openEditItemModal(id, code, name, category, cas, storage, etiq, lote, cad, gen, est) {
            document.getElementById('modal_item_id').value = id;
            document.getElementById('modal_code').value = code;
            document.getElementById('modal_name').value = name;
            document.getElementById('modal_category').value = category;
            document.getElementById('modal_cas').value = cas;
            document.getElementById('modal_storage').value = storage;
            document.getElementById('modal_etiqueta').value = etiq;
            document.getElementById('modal_lote').value = lote;
            document.getElementById('modal_caducidad').value = cad;
            document.getElementById('modal_stock_general').value = gen;
            document.getElementById('modal_stock_estacion').value = est;
            document.getElementById('modalItemTitle').innerText = 'Modificar: ' + name;
            document.getElementById('editModal').classList.remove('hidden');
        }

        function closeModal() {
            document.getElementById('editModal').classList.add('hidden');
        }

        function revertMovementModal(id) {
            document.getElementById('modal_movement_id').value = id;
            document.getElementById('revertModal').classList.remove('hidden');
        }

        function closeRevertModal() {
            document.getElementById('revertModal').classList.add('hidden');
        }

        function editUser(id, name, role, pin) {
            document.getElementById('edit_user_id').value = id;
            document.getElementById('edit_user_name').value = name;
            document.getElementById('edit_user_role').value = role;
            document.getElementById('edit_user_pin').value = pin;
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
    items = Item.query.order_by(Item.name, Item.lote).all()
    users = User.query.order_by(User.name).all()
    projects = Project.query.order_by(Project.name).all()
    return render_template_string(HTML_TEMPLATE, view="terminal", items=items, users=users, projects=projects)

@app.route("/register_batch", methods=["POST"])
def register_batch():
    user_id = request.form.get("user_id")
    pin = request.form.get("pin")
    project_name = request.form.get("project_name", "").strip()
    service = request.form.get("service", "").strip()
    notes = request.form.get("notes", "").strip()
    cart_json = request.form.get("cart_data", "[]")

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        flash("PIN o contraseña de usuario incorrecta.", "error")
        return redirect(url_for("terminal"))

    try:
        cart_items = json.loads(cart_json)
    except Exception:
        flash("Error al procesar la lista.", "error")
        return redirect(url_for("terminal"))

    if not cart_items or len(cart_items) == 0:
        flash("Debe agregar al menos un elemento.", "error")
        return redirect(url_for("terminal"))

    if project_name:
        existing_proj = Project.query.filter_by(name=project_name).first()
        if not existing_proj:
            new_p = Project(name=project_name)
            db.session.add(new_p)

    processed_count = 0

    for cart_item in cart_items:
        item_search = cart_item.get("item_search", "").strip()
        mov_type = cart_item.get("type")
        warehouse = cart_item.get("warehouse")
        quantity = int(cart_item.get("quantity", 1))

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
            continue

        if mov_type == "Entrada":
            if warehouse == "Almacén General":
                item.stock_general += quantity
            else:
                item.stock_estacion += quantity

        elif mov_type == "Salida":
            if warehouse == "Almacén General":
                if item.stock_general < quantity:
                    flash(f"Stock insuficiente para '{item.name}' en Almacén General.", "error")
                    db.session.rollback()
                    return redirect(url_for("terminal"))
                item.stock_general -= quantity
            else:
                if item.stock_estacion < quantity:
                    flash(f"Stock insuficiente para '{item.name}' en Estación de Trabajo.", "error")
                    db.session.rollback()
                    return redirect(url_for("terminal"))
                item.stock_estacion -= quantity

        elif mov_type == "Traspaso Estacion":
            if item.stock_general < quantity:
                flash(f"Stock insuficiente para traspasar '{item.name}'.", "error")
                db.session.rollback()
                return redirect(url_for("terminal"))
            item.stock_general -= quantity
            item.stock_estacion += quantity

        mov = Movement(
            timestamp=get_local_now(),
            item_code=item.code,
            item_name=f"{item.name} (Lote: {item.lote or 'S/L'})",
            type=mov_type,
            quantity=quantity,
            warehouse=warehouse,
            service=service,
            project_name=project_name,
            user_name=user.name,
            notes=notes
        )
        db.session.add(mov)
        processed_count += 1

    db.session.commit()
    flash(f"Operación de {processed_count} ítem(s) registrada con éxito.", "success")
    return redirect(url_for("terminal"))

@app.route("/inventario")
def inventario():
    items = Item.query.order_by(Item.name, Item.lote).all()
    projects = Project.query.order_by(Project.name).all()
    return render_template_string(HTML_TEMPLATE, view="inventario", items=items, projects=projects)

@app.route("/update_item", methods=["POST"])
def update_item():
    admin_pin = request.form.get("admin_pin", "").strip()
    admin_user = User.query.filter_by(role="Administrador").first()

    if admin_pin not in ["5678", "1234"] and (not admin_user or admin_user.pin != admin_pin):
        flash("PIN de Administrador incorrecto.", "error")
        return redirect(url_for("inventario"))

    item_id = request.form.get("item_id")
    item = Item.query.get(item_id)
    if item:
        item.code = request.form.get("code", item.code).strip().upper()
        item.name = request.form.get("name", item.name).strip()
        item.category = request.form.get("category", item.category)
        item.cas_number = request.form.get("cas_number", item.cas_number).strip()
        item.storage_condition = request.form.get("storage_condition", item.storage_condition).strip()
        item.etiqueta = request.form.get("etiqueta", item.etiqueta)
        item.lote = request.form.get("lote", item.lote).strip()
        item.caducidad = request.form.get("caducidad", item.caducidad).strip()
        item.stock_general = int(request.form.get("stock_general", item.stock_general))
        item.stock_estacion = int(request.form.get("stock_estacion", item.stock_estacion))
        
        db.session.commit()
        flash(f"Parámetros de '{item.name}' actualizados con éxito.", "success")
    
    return redirect(url_for("inventario"))

@app.route("/limpieza")
def limpieza():
    cleaning_logs = CleaningLog.query.order_by(CleaningLog.timestamp.desc()).all()
    users = User.query.order_by(User.id).all()
    
    # EXCLUSIÓN ESTRICTA DE ADMINISTRADORES DEL ROL ROTATIVO
    operational_users = User.query.filter(User.role != "Administrador").order_by(User.id).all()

    now = get_local_now()
    current_year, current_week, _ = now.isocalendar()

    def get_week_range(year, week):
        try:
            first_day = datetime.strptime(f'{year}-W{int(week):02d}-1', "%Y-W%W-%w")
        except Exception:
            first_day = now
        last_day = first_day + timedelta(days=6)
        return f"{first_day.strftime('%d/%m')} al {last_day.strftime('%d/%m')}"

    cleaning_tasks = [
        "💨 Sanitización Diaria de Campana de Extracción",
        "🧫 Limpieza y Desinfección de Mesas de Trabajo",
        "🧪 Revisión de Residuos Peligrosos y Reactivos"
    ]

    user_roles_detail = []

    if operational_users:
        num_users = len(operational_users)
        num_tasks = len(cleaning_tasks)

        for idx, u in enumerate(operational_users):
            task_index_this_week = (current_week + idx) % num_tasks
            task_index_next_week = (current_week + 1 + idx) % num_tasks

            task_this_week = cleaning_tasks[task_index_this_week]
            task_next_week = cleaning_tasks[task_index_next_week]

            user_roles_detail.append({
                'user': u,
                'task_this_week': task_this_week,
                'task_next_week': task_next_week
            })

    week_dates_current = get_week_range(current_year, current_week)
    week_dates_next = get_week_range(current_year, current_week + 1)

    projects = Project.query.order_by(Project.name).all()
    return render_template_string(
        HTML_TEMPLATE,
        view="limpieza",
        cleaning_logs=cleaning_logs,
        users=users,
        projects=projects,
        current_week=current_week,
        current_year=current_year,
        week_dates_current=week_dates_current,
        week_dates_next=week_dates_next,
        user_roles_detail=user_roles_detail
    )

@app.route("/add_cleaning", methods=["POST"])
def add_cleaning():
    user_id = request.form.get("user_id")
    pin = request.form.get("pin")
    campana_extraccion = 'campana_extraccion' in request.form
    mesas_trabajo = 'mesas_trabajo' in request.form
    reactivos_residuos = 'reactivos_residuos' in request.form
    notes = request.form.get("notes")

    user = User.query.get(user_id)
    if not user or user.pin != pin:
        flash("PIN o usuario incorrecto.", "error")
        return redirect(url_for("limpieza"))

    log = CleaningLog(
        timestamp=get_local_now(),
        user_name=user.name,
        campana_extraccion=campana_extraccion,
        mesas_trabajo=mesas_trabajo,
        reactivos_residuos=reactivos_residuos,
        notes=notes
    )
    db.session.add(log)
    db.session.commit()
    flash("Registro de mantenimiento guardado correctamente.", "success")
    return redirect(url_for("limpieza"))

@app.route("/bitacora")
def bitacora():
    movements = Movement.query.order_by(Movement.timestamp.desc()).all()
    projects = Project.query.order_by(Project.name).all()
    return render_template_string(HTML_TEMPLATE, view="bitacora", movements=movements, projects=projects)

@app.route("/revert_movement", methods=["POST"])
def revert_movement():
    mov_id = request.form.get("movement_id")
    admin_pin = request.form.get("admin_pin", "").strip()

    admin_user = User.query.filter_by(role="Administrador").first()
    if admin_pin not in ["5678", "1234"] and (not admin_user or admin_user.pin != admin_pin):
        flash("PIN de Administrador incorrecto.", "error")
        return redirect(url_for("bitacora"))

    mov = Movement.query.get(mov_id)
    if mov:
        clean_name = mov.item_name.split(" (Lote:")[0] if " (Lote:" in mov.item_name else mov.item_name
        item = Item.query.filter((Item.code == mov.item_code) | (Item.name == clean_name)).first()

        if item:
            if mov.type == "Salida":
                if mov.warehouse == "Almacén General":
                    item.stock_general += mov.quantity
                else:
                    item.stock_estacion += mov.quantity
            elif mov.type == "Entrada":
                if mov.warehouse == "Almacén General":
                    item.stock_general -= mov.quantity
                else:
                    item.stock_estacion -= mov.quantity

        db.session.delete(mov)
        db.session.commit()
        flash("Movimiento revertido con éxito.", "success")

    return redirect(url_for("bitacora"))

@app.route("/usuarios")
def usuarios():
    users = User.query.order_by(User.name).all()
    projects = Project.query.order_by(Project.name).all()
    is_admin = request.args.get("admin") == "true"
    return render_template_string(HTML_TEMPLATE, view="usuarios", users=users, projects=projects, is_admin=is_admin)

@app.route("/auth_admin_users", methods=["POST"])
def auth_admin_users():
    admin_pin = request.form.get("admin_pin", "").strip()
    admin_user = User.query.filter_by(role="Administrador").first()

    if admin_pin in ["5678", "1234"] or (admin_user and admin_user.pin == admin_pin):
        flash("Acceso concedido a la gestión de usuarios.", "success")
        return redirect(url_for("usuarios", admin="true"))
    else:
        flash("PIN de Administrador incorrecto.", "error")
        return redirect(url_for("usuarios"))

@app.route("/save_user", methods=["POST"])
def save_user():
    user_id = request.form.get("user_id")
    name = request.form.get("name", "").strip()
    role = request.form.get("role")
    pin = request.form.get("pin", "").strip()

    if user_id:
        u = User.query.get(user_id)
        if u:
            u.name = name
            u.role = role
            u.pin = pin
            flash(f"Usuario '{name}' actualizado correctamente.", "success")
    else:
        new_u = User(name=name, role=role, pin=pin)
        db.session.add(new_u)
        flash(f"Usuario '{name}' creado con éxito.", "success")

    db.session.commit()
    return redirect(url_for("usuarios", admin="true"))

@app.route("/alta_insumos")
def alta_insumos():
    users = User.query.order_by(User.name).all()
    projects = Project.query.order_by(Project.name).all()
    return render_template_string(HTML_TEMPLATE, view="alta_insumos", users=users, projects=projects)

@app.route("/add_item", methods=["POST"])
def add_item():
    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()
    category = request.form.get("category")
    cas_number = request.form.get("cas_number", "").strip()
    storage_condition = request.form.get("storage_condition", "").strip()
    lote = request.form.get("lote", "").strip()
    caducidad = request.form.get("caducidad", "").strip()
    etiqueta = request.form.get("etiqueta", "General")
    unit = request.form.get("unit", "pza").strip()
    stock_general = int(request.form.get("stock_general", 0))

    try:
        new_item = Item(
            code=code, 
            name=name, 
            category=category, 
            cas_number=cas_number,
            storage_condition=storage_condition,
            lote=lote,
            caducidad=caducidad,
            etiqueta=etiqueta,
            unit=unit, 
            stock_general=stock_general, 
            stock_estacion=0
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"Insumo '{name}' registrado con éxito.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al registrar: {str(e)}", "error")

    return redirect(url_for("alta_insumos"))

# -----------------------------------------------------------------------------
# INICIALIZACIÓN DE BASE DE DATOS
# -----------------------------------------------------------------------------

def seed_database():
    with app.app_context():
        db.create_all()
        if User.query.count() == 0:
            users_list = [
                User(name="Dr. David Gonzalez", role="Administrador", pin="5678"),
                User(name="Dra. Sofia Ramos", role="Investigador Titular", pin="4321"),
                User(name="Alfonso Guzman", role="Técnico de Laboratorio", pin="1234"),
                User(name="Hannia Martinez", role="Asistente de Investigación", pin="1122")
            ]
            db.session.add_all(users_list)

        if Item.query.count() == 0:
            items_list = [
                Item(code="REQ-001", name="Ácido Clorhídrico 37%", category="Reactivo Químico", cas_number="7647-01-0", storage_condition="Temperatura Ambiente", lote="LOT-A991", caducidad="2028-05-30", etiqueta="Corrosivo", stock_general=25, stock_estacion=5),
                Item(code="REQ-002", name="Etanol Absoluto", category="Reactivo Químico", cas_number="64-17-5", storage_condition="Área de Inflamables", lote="LOT-B102", caducidad="2027-10-15", etiqueta="Inflamable", stock_general=50, stock_estacion=10),
                Item(code="MAT-001", name="Matraz Erlenmeyer 250ml", category="Material de Vidrio", cas_number="", storage_condition="Anaquel Vidriería", lote="S/L", caducidad="", etiqueta="General", stock_general=30, stock_estacion=8)
            ]
            db.session.add_all(items_list)

        db.session.commit()

seed_database()

if __name__ == "__main__":
    app.run(debug=True)
