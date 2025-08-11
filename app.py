# Sistema de Facturación de Agua para Edificio
# Archivo: app.py

from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# Configuración de la base de datos
def init_db():
    """Inicializa la base de datos SQLite"""
    conn = sqlite3.connect('facturacion_agua.db')
    cursor = conn.cursor()
    
    # Tabla para departamentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla para registros de facturación
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            mes_facturacion TEXT NOT NULL,
            medidor_principal_m3 REAL NOT NULL,
            monto_total REAL NOT NULL,
            total_departamentos_m3 REAL NOT NULL,
            diferencia_m3 REAL NOT NULL
        )
    ''')
    
    # Tabla para consumos individuales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facturacion_id INTEGER,
            departamento_id INTEGER,
            consumo_m3 REAL NOT NULL,
            monto_pagar REAL NOT NULL,
            FOREIGN KEY (facturacion_id) REFERENCES facturacion (id),
            FOREIGN KEY (departamento_id) REFERENCES departamentos (id)
        )
    ''')
    
    # Insertar departamentos predeterminados si no existen
    departamentos_default = [
        'Departamento 101', 'Departamento 201', 'Departamento 301',
        'Departamento 401', 'Departamento 501', 'Departamento 502',
        'Departamento 601', 'Departamento 602'
    ]
    
    for dept in departamentos_default:
        cursor.execute('INSERT OR IGNORE INTO departamentos (nombre) VALUES (?)', (dept,))
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Obtiene conexión a la base de datos"""
    conn = sqlite3.connect('facturacion_agua.db')
    conn.row_factory = sqlite3.Row
    return conn

def calcular_distribucion(medidor_principal, monto_total, consumos_individuales):
    """
    Calcula la distribución proporcional del costo total entre departamentos
    usando porcentajes basados en el total de consumos de departamentos
    
    Args:
        medidor_principal (float): Consumo total del medidor principal en m³
        monto_total (float): Monto total a pagar
        consumos_individuales (list): Lista de consumos por departamento en m³
    
    Returns:
        tuple: (costo_por_m3, pagos_por_departamento, total_departamentos)
    """
    total_departamentos = sum(consumos_individuales)
    
    # Calcular costo por m³ basado en el medidor principal
    costo_por_m3 = monto_total / medidor_principal
    
    # Calcular pagos usando método de porcentajes
    pagos = []
    for consumo in consumos_individuales:
        # Calcular porcentaje del consumo individual sobre el total de departamentos
        porcentaje = (consumo / total_departamentos) if total_departamentos > 0 else 0
        # Aplicar ese porcentaje al monto total
        pago = porcentaje * monto_total
        pagos.append(round(pago, 2))
    
    # Ajustar redondeo para que la suma sea exacta
    diferencia = monto_total - sum(pagos)
    if abs(diferencia) > 0.01:  # Si hay diferencia significativa por redondeo
        # Agregar la diferencia al departamento con mayor consumo
        max_index = consumos_individuales.index(max(consumos_individuales))
        pagos[max_index] += diferencia
        pagos[max_index] = round(pagos[max_index], 2)
    
    return costo_por_m3, pagos, total_departamentos

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/nueva_facturacion')
def nueva_facturacion():
    """Formulario para nueva facturación"""
    conn = get_db_connection()
    departamentos = conn.execute('SELECT * FROM departamentos WHERE activo = 1 ORDER BY nombre').fetchall()
    conn.close()
    return render_template('nueva_facturacion.html', departamentos=departamentos)

@app.route('/procesar_facturacion', methods=['POST'])
def procesar_facturacion():
    """Procesa nueva facturación"""
    try:
        # Obtener datos del formulario
        mes_facturacion = request.form['mes_facturacion']
        medidor_principal = float(request.form['medidor_principal'])
        monto_total = float(request.form['monto_total'])
        
        conn = get_db_connection()
        departamentos = conn.execute('SELECT * FROM departamentos WHERE activo = 1 ORDER BY nombre').fetchall()
        
        # Obtener consumos individuales
        consumos = []
        departamentos_ids = []
        
        for dept in departamentos:
            consumo = float(request.form.get(f'consumo_{dept["id"]}', 0))
            consumos.append(consumo)
            departamentos_ids.append(dept['id'])
        
        total_departamentos = sum(consumos)
        diferencia = medidor_principal - total_departamentos
        
        # Calcular distribución
        costo_por_m3, pagos, _ = calcular_distribucion(medidor_principal, monto_total, consumos)
        
        # Guardar en base de datos
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO facturacion (mes_facturacion, medidor_principal_m3, monto_total, 
                                   total_departamentos_m3, diferencia_m3)
            VALUES (?, ?, ?, ?, ?)
        ''', (mes_facturacion, medidor_principal, monto_total, total_departamentos, diferencia))
        
        facturacion_id = cursor.lastrowid
        
        # Guardar consumos individuales
        for i, dept_id in enumerate(departamentos_ids):
            cursor.execute('''
                INSERT INTO consumos (facturacion_id, departamento_id, consumo_m3, monto_pagar)
                VALUES (?, ?, ?, ?)
            ''', (facturacion_id, dept_id, consumos[i], pagos[i]))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('ver_facturacion', facturacion_id=facturacion_id))
        
    except Exception as e:
        return f"Error al procesar facturación: {str(e)}", 400

@app.route('/ver_facturacion/<int:facturacion_id>')
def ver_facturacion(facturacion_id):
    """Ver detalles de una facturación específica"""
    conn = get_db_connection()
    
    # Obtener datos de facturación
    facturacion = conn.execute('SELECT * FROM facturacion WHERE id = ?', (facturacion_id,)).fetchone()
    
    if not facturacion:
        conn.close()
        return "Facturación no encontrada", 404
    
    # Obtener consumos con nombres de departamentos
    consumos = conn.execute('''
        SELECT c.*, d.nombre as departamento_nombre
        FROM consumos c
        JOIN departamentos d ON c.departamento_id = d.id
        WHERE c.facturacion_id = ?
        ORDER BY d.nombre
    ''', (facturacion_id,)).fetchall()
    
    conn.close()
    
    return render_template('ver_facturacion.html', facturacion=facturacion, consumos=consumos)

@app.route('/historial')
def historial():
    """Ver historial de facturaciones"""
    conn = get_db_connection()
    facturaciones = conn.execute('''
        SELECT id, fecha_registro, mes_facturacion, medidor_principal_m3, 
               monto_total, total_departamentos_m3, diferencia_m3
        FROM facturacion 
        ORDER BY fecha_registro DESC
    ''').fetchall()
    conn.close()
    
    return render_template('historial.html', facturaciones=facturaciones)

@app.route('/gestionar_departamentos')
def gestionar_departamentos():
    """Gestionar departamentos"""
    conn = get_db_connection()
    departamentos = conn.execute('SELECT * FROM departamentos ORDER BY nombre').fetchall()
    conn.close()
    return render_template('gestionar_departamentos.html', departamentos=departamentos)

@app.route('/agregar_departamento', methods=['POST'])
def agregar_departamento():
    """Agregar nuevo departamento"""
    nombre = request.form['nombre'].strip()
    if nombre:
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO departamentos (nombre) VALUES (?)', (nombre,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Departamento ya existe
        conn.close()
    
    return redirect(url_for('gestionar_departamentos'))

@app.route('/toggle_departamento/<int:dept_id>')
def toggle_departamento(dept_id):
    """Activar/desactivar departamento"""
    conn = get_db_connection()
    dept = conn.execute('SELECT activo FROM departamentos WHERE id = ?', (dept_id,)).fetchone()
    if dept:
        nuevo_estado = not dept['activo']
        conn.execute('UPDATE departamentos SET activo = ? WHERE id = ?', (nuevo_estado, dept_id))
        conn.commit()
    conn.close()
    
    return redirect(url_for('gestionar_departamentos'))

# Filtros personalizados para templates
@app.template_filter('currency')
def currency_filter(value):
    """Formato de moneda peruana"""
    return f"S/ {value:,.2f}"

@app.template_filter('volume')
def volume_filter(value):
    """Formato de volumen"""
    return f"{value:.2f} m³"

if __name__ == '__main__':
    # Crear directorio templates si no existe
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Inicializar base de datos
    init_db()
    
    # Ejecutar aplicación
    app.run(debug=True, host='0.0.0.0', port=5000)