from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from reportlab.pdfgen import canvas
import io
import os


# Configuración explícita para que Render no se pierda
app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates')

app.secret_key = "123456789"

# ---------------------------
# Conexión a la base de datos
# ---------------------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------
# Crear tablas si no existen
# ---------------------------
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS docentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            password TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alumnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            materia TEXT,
            escuela TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            nota REAL,
            FOREIGN KEY(alumno_id) REFERENCES alumnos(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS carga_horaria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            horas_totales INTEGER,
            horas_dictadas INTEGER,
            FOREIGN KEY(alumno_id) REFERENCES alumnos(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS progreso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            asistencia REAL,
            trabajos REAL,
            participacion REAL,
            FOREIGN KEY(alumno_id) REFERENCES alumnos(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rubricas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            descripcion TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS criterios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rubrica_id INTEGER,
            criterio TEXT,
            peso REAL,
            FOREIGN KEY(rubrica_id) REFERENCES rubricas(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            criterio_id INTEGER,
            nivel INTEGER,
            FOREIGN KEY(alumno_id) REFERENCES alumnos(id),
            FOREIGN KEY(criterio_id) REFERENCES criterios(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------------------
# LOGIN
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

# ---------------------------
# PANEL PRINCIPAL
# ---------------------------
@app.route("/inicio")
def inicio():
    if "docente" not in session:
        return redirect("/")

    conn = get_db()
    alumnos = conn.execute("SELECT * FROM alumnos").fetchall()
    return render_template("index.html", alumnos=alumnos)

# ---------------------------
# AGREGAR ALUMNO
# ---------------------------
@app.route("/agregar", methods=["GET", "POST"])
def agregar():
    if request.method == "POST":
        nombre = request.form["nombre"]
        materia = request.form["materia"]
        escuela = request.form["escuela"]

        conn = get_db()
        conn.execute("INSERT INTO alumnos (nombre, materia, escuela) VALUES (?, ?, ?)",
                     (nombre, materia, escuela))
        conn.commit()
        return redirect("/inicio")

    return render_template("alumno_form.html")

# ---------------------------
# FICHA DEL ALUMNO (tarjeta + pestañas)
# ---------------------------
@app.route("/alumno/<int:id>")
def alumno_ficha(id):
    conn = get_db()
    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    return render_template("alumno_ficha.html", alumno=alumno)

# ---------------------------
# PESTAÑA: DATOS
# ---------------------------
@app.route("/alumno/<int:id>/datos", methods=["GET", "POST"])
def ficha_datos(id):
    conn = get_db()
    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()

    if request.method == "POST":
        nombre = request.form["nombre"]
        materia = request.form["materia"]
        escuela = request.form["escuela"]

        conn.execute("""
            UPDATE alumnos SET nombre=?, materia=?, escuela=? WHERE id=?
        """, (nombre, materia, escuela, id))
        conn.commit()
        return redirect(f"/alumno/{id}")

    return render_template("ficha_datos.html", alumno=alumno)

# ---------------------------
# PESTAÑA: NOTAS
# ---------------------------
@app.route("/alumno/<int:id>/notas", methods=["GET", "POST"])
def ficha_notas(id):
    conn = get_db()

    if request.method == "POST":
        notas_str = request.form["notas"]
        notas = [float(n.strip()) for n in notas_str.split(",") if n.strip()]

        conn.execute("DELETE FROM notas WHERE alumno_id=?", (id,))
        for n in notas:
            conn.execute("INSERT INTO notas (alumno_id, nota) VALUES (?, ?)", (id, n))
        conn.commit()

        return redirect(f"/alumno/{id}/notas")

    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    notas = conn.execute("SELECT nota FROM notas WHERE alumno_id=?", (id,)).fetchall()
    notas_lista = [n["nota"] for n in notas]

    return render_template("ficha_notas.html", alumno=alumno, notas=notas_lista)

# ---------------------------
# PESTAÑA: CARGA HORARIA
# ---------------------------
@app.route("/alumno/<int:id>/carga", methods=["GET", "POST"])
def ficha_carga(id):
    conn = get_db()

    carga = conn.execute(
        "SELECT * FROM carga_horaria WHERE alumno_id=?", (id,)
    ).fetchone()

    if request.method == "POST":
        horas_totales = int(request.form["horas_totales"])
        horas_dictadas = int(request.form["horas_dictadas"])

        if carga:
            conn.execute("""
                UPDATE carga_horaria SET horas_totales=?, horas_dictadas=? WHERE alumno_id=?
            """, (horas_totales, horas_dictadas, id))
        else:
            conn.execute("""
                INSERT INTO carga_horaria (alumno_id, horas_totales, horas_dictadas)
                VALUES (?, ?, ?)
            """, (id, horas_totales, horas_dictadas))

        conn.commit()
        return redirect(f"/alumno/{id}/carga")

    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    return render_template("ficha_carga.html", alumno=alumno, carga=carga)

# ---------------------------
# PESTAÑA: PROGRESO
# ---------------------------
@app.route("/alumno/<int:id>/progreso", methods=["GET", "POST"])
def ficha_progreso(id):
    conn = get_db()

    progreso = conn.execute(
        "SELECT * FROM progreso WHERE alumno_id=?", (id,)
    ).fetchone()

    if request.method == "POST":
        asistencia = float(request.form["asistencia"])
        trabajos = float(request.form["trabajos"])
        participacion = float(request.form["participacion"])

        if progreso:
            conn.execute("""
                UPDATE progreso SET asistencia=?, trabajos=?, participacion=? WHERE alumno_id=?
            """, (asistencia, trabajos, participacion, id))
        else:
            conn.execute("""
                INSERT INTO progreso (alumno_id, asistencia, trabajos, participacion)
                VALUES (?, ?, ?, ?)
            """, (id, asistencia, trabajos, participacion))

        conn.commit()
        return redirect(f"/alumno/{id}/progreso")

    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    return render_template("ficha_progreso.html", alumno=alumno, progreso=progreso)

# ---------------------------
# PESTAÑA: RÚBRICAS
# ---------------------------
@app.route("/alumno/<int:id>/rubricas")
def ficha_rubricas(id):
    conn = get_db()
    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    rubricas = conn.execute("SELECT * FROM rubricas").fetchall()
    return render_template("ficha_rubricas.html", alumno=alumno, rubricas=rubricas)

# ---------------------------
# PDF DEL ALUMNO
# ---------------------------
@app.route("/pdf/<int:id>")
def pdf(id):
    conn = get_db()
    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (id,)).fetchone()
    notas = conn.execute("SELECT nota FROM notas WHERE alumno_id=?", (id,)).fetchall()
    notas_lista = [n["nota"] for n in notas]
    promedio = sum(notas_lista) / len(notas_lista) if notas_lista else 0

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "Boletín de Calificaciones")

    p.setFont("Helvetica", 12)
    p.drawString(100, 760, f"Alumno: {alumno['nombre']}")
    p.drawString(100, 740, f"Materia: {alumno['materia']}")
    p.drawString(100, 720, f"Escuela: {alumno['escuela']}")
    p.drawString(100, 700, f"Notas: {notas_lista}")
    p.drawString(100, 680, f"Promedio: {promedio:.2f}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="boletin.pdf")

# ---------------------------
# EJECUTAR SERVIDOR
# ---------------------------

if __name__ == "__main__":
    app.run(debug=True)   # solo para desarrollo