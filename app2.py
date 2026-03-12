from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from reportlab.pdfgen import canvas
import io
import os

app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates')

app.secret_key = "DGE_Proyect_2026_Seguro" # Clave para evitar alertas de Chrome

# ---------------------------
# Conexión a la base de datos
# ---------------------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------
# Crear tablas si no existen (Estructura Técnica)
# ---------------------------
def init_db():
    conn = get_db()
    # Tabla de Docentes (para el Login)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS docentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            password TEXT
        )
    """)
    # Tabla de Alumnos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alumnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            materia TEXT,
            escuela TEXT
        )
    """)
    # NUEVA TABLA DE NOTAS (Con Actividad y Fecha)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            actividad TEXT,
            fecha TEXT,
            valor REAL,
            observaciones TEXT,
            FOREIGN KEY(alumno_id) REFERENCES alumnos(id)
        )
    """)
    conn.commit()
    conn.close()

# ---------------------------
# Función de Auto-Registro (Solución al Login)
# ---------------------------
def crear_usuario_inicial():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    # Verificamos si existe en la tabla 'docentes'
    cursor.execute("SELECT * FROM docentes WHERE usuario = ?", ('admin',))
    if not cursor.fetchone():
        cursor.execute("INSERT OR IGNORE INTO docentes (usuario, password) VALUES (?, ?)",
                       ('admin', '12345'))
        conn.commit()
        print(">>> CONFIGURACIÓN: Usuario 'admin' / '12345' creado con éxito.")
    conn.close()

# Inicializamos la DB y el usuario al arrancar
init_db()
crear_usuario_inicial()

# ---------------------------
# RUTAS DE LOGIN Y SISTEMA
# ---------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]
        conn = get_db()
        docente = conn.execute(
            "SELECT * FROM docentes WHERE usuario=? AND password=?",
            (usuario, password)
        ).fetchone()
        conn.close()

        if docente:
            session["docente"] = usuario
            return redirect("/inicio")
        else:
            return render_template("login.html", error="Credenciales incorrectas")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/inicio")
def inicio():
    if "docente" not in session:
        return redirect("/")
    conn = get_db()
    alumnos = conn.execute("SELECT * FROM alumnos").fetchall()
    conn.close()
    return render_template("index.html", alumnos=alumnos)

# ---------------------------
# GESTIÓN DE ALUMNOS (Carga y Borrado)
# ---------------------------

@app.route("/agregar", methods=["GET", "POST"])
def agregar():
    
    if "docente" not in session: 
        return redirect("/")
    if request.method == "POST":
        nombre = request.form["nombre"]
        materia = request.form["materia"]
        escuela = request.form["escuela"]
        conn = get_db()
        conn.execute("INSERT INTO alumnos (nombre, materia, escuela) VALUES (?, ?, ?)",
                     (nombre, materia, escuela))
        conn.commit()
        conn.close()
        return redirect("/inicio")
    return render_template("alumno_form.html")

@app.route("/eliminar/<int:id>")
def eliminar_alumno(id):
    if "docente" not in session: 
        return redirect("/")
    conn = get_db()
    conn.execute("DELETE FROM alumnos WHERE id = ?", (id,))
    conn.execute("DELETE FROM notas WHERE alumno_id = ?", (id,)) # Borra sus notas también
    conn.commit()
    conn.close()
    return redirect("/inicio")

# ---------------------------
# REGISTRO DE NOTAS (Efecto Excel)
# ---------------------------

@app.route("/alumno/<int:id>/notas", methods=["GET", "POST"])
def ficha_notas(id):
    if "docente" not in session: 
        return redirect("/")
    conn = get_db()
    
    if request.method == "POST":
        actividad = request.form.get("actividad")
        fecha = request.form.get("fecha")
        valor = request.form.get("valor")
        obs = request.form.get("obs")
        
        conn.execute("""
            INSERT INTO notas (alumno_id, actividad, fecha, valor, observaciones) 
            VALUES (?, ?, ?, ?, ?)
        """, (id, actividad, fecha, valor, obs))
        conn.commit()
        return redirect(f"/alumno/{id}/notas")

    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    notas = conn.execute("SELECT * FROM notas WHERE alumno_id=? ORDER BY fecha DESC", (id,)).fetchall()
    conn.close()
    return render_template("ficha_notas.html", alumno=alumno, notas=notas)

@app.route("/eliminar_nota/<int:nota_id>/<int:alumno_id>")
def eliminar_nota(nota_id, alumno_id):
    if "docente" not in session: 
        return redirect("/")
    conn = get_db()
    conn.execute("DELETE FROM notas WHERE id = ?", (nota_id,))
    conn.commit()
    conn.close()
    return redirect(f"/alumno/{alumno_id}/notas")

# ---------------------------
# FICHA Y PDF
# ---------------------------

@app.route("/alumno/<int:id>")
def alumno_ficha(id):
    if "docente" not in session: 
        return redirect("/")
    conn = get_db()
    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template("alumno_ficha.html", alumno=alumno)

@app.route("/pdf/<int:id>")
def pdf(id):
    conn = get_db()
    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    notas = conn.execute("SELECT valor FROM notas WHERE alumno_id=?", (id,)).fetchall()
    notas_lista = [n["valor"] for n in notas]
    promedio = sum(notas_lista) / len(notas_lista) if notas_lista else 0
    conn.close()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "Boletín de Calificaciones")
    p.setFont("Helvetica", 12)
    p.drawString(100, 760, f"Alumno: {alumno['nombre']}")
    p.drawString(100, 740, f"Materia: {alumno['materia']}")
    p.drawString(100, 720, f"Escuela: {alumno['escuela']}")
    p.drawString(100, 680, f"Promedio Final: {promedio:.2f}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"boletin_{alumno['nombre']}.pdf")

if __name__ == "__main__":
    # Configuración para Render y Local
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)