from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from db import get_connection
from datetime import date, datetime, timedelta
from io import BytesIO
from fpdf import FPDF
import MySQLdb
import MySQLdb.cursors


from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = "supersecretkey"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True

@app.before_request
def make_session_permanent():
    session.permanent = True

mysql = get_connection(app)

@app.teardown_appcontext
def close_db(error):
    from flask import g
    db_conn = g.pop('db_conn', None)
    if db_conn is not None and db_conn.open:
        db_conn.close()

# -------------------- Image Compression Utility --------------------
from PIL import Image
import io

def compress_image_data(file_name, file_data, max_dim=1200, quality=60):
    ext = file_name.lower().split('.')[-1]
    if ext not in ['jpg', 'jpeg', 'png']:
        return file_data
    try:
        img = Image.open(io.BytesIO(file_data))
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
            
        width, height = img.size
        if width > max_dim or height > max_dim:
            if width > height:
                height = int((height * max_dim) / width)
                width = max_dim
            else:
                width = int((width * max_dim) / height)
                height = max_dim
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=quality, optimize=True)
        return out.getvalue()
    except Exception as e:
        print("Failed to compress image:", e)
        return file_data

# -------------------- Cloudinary Configuration & Utility --------------------
import cloudinary
import cloudinary.uploader
import os

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def upload_to_cloudinary(file_name, file_data, folder="careconnect"):
    try:
        # Upload binary data directly to Cloudinary
        upload_result = cloudinary.uploader.upload(
            BytesIO(file_data),
            folder=folder,
            resource_type="auto"
        )
        return upload_result.get("secure_url")
    except Exception as e:
        print("Cloudinary upload failed for", file_name, ":", e)
        return None

# -------------------- Home --------------------
@app.route("/")
def home():
    return render_template("home.html")

# -------------------- Admin Login --------------------
@app.route("/admin/login")
def admin_login():
    return render_template("admin_login.html")
# -------------------- Receptionist Login --------------------
@app.route("/receptionist/login", methods=["GET", "POST"])
def receptionist_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM receptionists WHERE username=%s AND password=%s", (username, password))
        receptionist = cur.fetchone()
        cur.close()

        if receptionist:
            session.pop("doctor_logged_in", None)
            session.pop("doctor_name", None)
            session.pop("lab_logged_in", None)
            session.pop("lab_name", None)
            session["receptionist_logged_in"] = True
            session["receptionist_id"] = receptionist["receptionist_id"]
            session["receptionist_name"] = receptionist["name"]
            return redirect(url_for("receptionist_dashboard"))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for("receptionist_login"))

    return render_template("receptionist_login.html")

@app.route("/receptionist/dashboard")
def receptionist_dashboard():
    if not session.get("receptionist_logged_in"):
        return redirect(url_for("receptionist_login"))
    return render_template("receptionist_dashboard.html")

@app.route("/receptionist/logout")
def receptionist_logout():
    session.clear()
    return redirect(url_for("receptionist_login"))

# -------------------- Search Patient --------------------
@app.route("/receptionist/search", methods=["GET", "POST"])
def search_patient():
    if request.method == "POST":
        aadhaar = request.form.get("aadhaar")
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM patients WHERE aadhaar = %s", (aadhaar,))
        patient = cursor.fetchone()
        cursor.close()

        if patient:
            return redirect(url_for("make_appointment", aadhaar=aadhaar))
        else:
            return redirect(url_for("register_patient", aadhaar=aadhaar))

    return render_template("search_patient.html")

# -------------------- Register Patient --------------------
@app.route("/receptionist/register", methods=["GET", "POST"])
def register_patient():
    if request.method == "POST":
        name = request.form.get("name")
        birth_date = request.form.get("birth_date")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        address = request.form.get("address")
        aadhaar = request.form.get("aadhaar")

        age = None
        if birth_date:
            birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d')
            age = (datetime.today() - birth_date_obj).days // 365

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO patients (aadhaar, name, age, gender, contact, address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (aadhaar, name, age, gender, phone, address))
        mysql.connection.commit()
        cursor.close()

        return redirect(url_for("make_appointment", aadhaar=aadhaar))

    aadhaar = request.args.get("aadhaar")
    return render_template("register_patient.html", aadhaar=aadhaar)

# -------------------- Make Appointment --------------------
@app.route("/receptionist/appointment", methods=["GET", "POST"])
def make_appointment():
    if request.method == "POST":
        aadhaar = request.form.get("aadhaar")
        department = request.form.get("department")
        doctor = request.form.get("doctor")
        amount = request.form.get("amount", "500.00")
        payment_method = request.form.get("payment_method", "Cash")

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT name, age, gender FROM patients WHERE aadhaar = %s", (aadhaar,))
        patient = cursor.fetchone()

        if not patient:
            return f"Error: No patient found with Aadhaar {aadhaar}"

        cursor.execute("""
            INSERT INTO appointments (aadhaar, department, doctor, appointment_date, amount, payment_method)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (aadhaar, department, doctor, appointment_date, amount, payment_method))
        mysql.connection.commit()
        cursor.close()

        return render_template("appointment_confirmation.html",
                               uhid=aadhaar,
                               name=patient["name"],
                               age=patient["age"],
                               gender=patient["gender"],
                               department=department,
                               doctor=doctor,
                               appointment_date=appointment_date,
                               valid_upto=(datetime.strptime(appointment_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
                               amount=f"{float(amount):,.2f}")

    aadhaar = request.args.get("aadhaar")
    min_date = date.today().isoformat()

    # Fetch active doctors from database
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT name, specialization FROM doctors")
    doctors = cursor.fetchall()
    cursor.close()

    # Group doctors by department
    doctors_by_dept = {}
    for doc in doctors:
        dept = doc["specialization"]
        if dept not in doctors_by_dept:
            doctors_by_dept[dept] = []
        doctors_by_dept[dept].append(doc["name"])

    return render_template("make_appointment.html", 
                           aadhaar=aadhaar, 
                           min_date=min_date, 
                           doctors_by_dept=doctors_by_dept)

# -------------------- Appointment PDF --------------------
@app.route("/receptionist/appointment/pdf/<aadhaar>")
def generate_pdf(aadhaar):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM patients WHERE aadhaar=%s", (aadhaar,))
    patient = cursor.fetchone()
    cursor.execute("SELECT * FROM appointments WHERE aadhaar=%s ORDER BY appointment_date DESC LIMIT 1", (aadhaar,))
    appointment = cursor.fetchone()
    cursor.close()

    pdf = FPDF()
    pdf.add_page()

    # Header
    pdf.set_fill_color(220, 230, 241)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 12, "CareConnect Hospital", ln=True, align="C", fill=True)

    pdf.set_font("Arial", 'I', 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, "Appointment Confirmation", ln=True, align="C")
    pdf.ln(10)

    # Info
    pdf.set_font("Arial", '', 12)
    pdf.set_text_color(0, 0, 0)

    pdf.cell(60, 10, f"Name: {patient['name']}", border=1)
    pdf.cell(60, 10, f"Age: {patient['age']}", border=1)
    pdf.cell(60, 10, f"Gender: {patient['gender']}", border=1, ln=True)

    pdf.cell(60, 10, f"Department: {appointment['department']}", border=1)
    pdf.cell(60, 10, f"Doctor: {appointment['doctor']}", border=1)
    pdf.cell(60, 10, f"Appointment Date: {appointment['appointment_date']}", border=1, ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 7, "Please arrive 10 minutes before your scheduled appointment. This confirmation is valid for one day only.", align='L')

    pdf_output = pdf.output(dest='S').encode('latin1')
    return send_file(BytesIO(pdf_output),
                     as_attachment=True,
                     download_name="appointment.pdf",
                     mimetype="application/pdf")

# -------------------- Doctor Login --------------------
@app.route("/doctor/login", methods=["GET", "POST"])
def doctor_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT doctor_id, username, password, name, specialization FROM doctors WHERE username=%s AND password=%s",
            (username, password),
        )
        doctor = cur.fetchone()
        cur.close()

        print("Doctor fetched:", doctor)  # Debugging

        if doctor:
            session.pop("lab_logged_in", None)
            session.pop("lab_name", None)
            session.pop("receptionist_logged_in", None)
            session.pop("receptionist_name", None)
            session["doctor_logged_in"] = True
            session["doctor_id"] = doctor[0]   # doctor_id
            session["doctor_name"] = doctor[3] # name
            session["specialization"] = doctor[4] # specialization
            return redirect(url_for("doctor_dashboard"))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for("doctor_login"))

    return render_template("doctor_login.html")





# -------------------- Doctor Dashboard --------------------
@app.route("/doctor/dashboard", methods=["GET", "POST"])
def doctor_dashboard():
    if not session.get("doctor_logged_in"):
        return redirect(url_for("doctor_login"))

    patient = None
    history = []
    reports = []
    aadhaar = None

    cur = mysql.connection.cursor()

    if request.method == "POST":
        # Search bar
        if "aadhaar" in request.form:
            aadhaar = request.form.get("aadhaar")
        # Recent patient panel
        elif "selected_aadhaar" in request.form:
            aadhaar = request.form.get("selected_aadhaar")

    if aadhaar:
        cur.execute("SELECT name, aadhaar, age, gender FROM patients WHERE aadhaar = %s", (aadhaar,))
        patient = cur.fetchone()
        if patient:
            patient = {
                "name": patient[0],
                "aadhaar": patient[1],
                "age": patient[2],
                "gender": patient[3]
            }

            cur.execute("""
                SELECT visit_date, diagnosis, prescription, advised_tests, doctor_name, history_id, prescription_image_name
                FROM patient_history WHERE aadhaar = %s
                ORDER BY visit_date DESC, history_id DESC
            """, (aadhaar,))
            history = [
                {
                    "visit_date": h[0],
                    "diagnosis": h[1],
                    "prescription": h[2],
                    "advised_tests": h[3],
                    "doctor_name": h[4],
                    "history_id": h[5],
                    "prescription_image_name": h[6]
                }
                for h in cur.fetchall()
            ]

            cur.execute("""
                SELECT id, report_date, report_type, uploaded_by
                FROM lab_reports WHERE aadhaar = %s
                ORDER BY report_date DESC, id DESC
            """, (aadhaar,))
            reports = [
                {"id": r[0], "report_date": r[1], "report_type": r[2], "uploaded_by": r[3]}
                for r in cur.fetchall()
            ]

    # Fetch doctor's assigned patients (recent 20) from appointments
    doctor_name = session.get("doctor_name")
    cur.execute("""
        SELECT p.name, p.aadhaar
        FROM appointments a
        JOIN patients p ON a.aadhaar = p.aadhaar
        WHERE a.doctor = %s
        GROUP BY p.name, p.aadhaar
        ORDER BY MAX(a.appointment_date) DESC
        LIMIT 20
    """, (doctor_name,))
    recent_patients = [{"name": rp[0], "aadhaar": rp[1]} for rp in cur.fetchall()]

    cur.close()

    return render_template("doctor_dashboard.html",
                           patient=patient,
                           history=history,
                           reports=reports,
                           recent_patients=recent_patients)

# -------------------- Save Today's Data --------------------
@app.route("/doctor/save_history", methods=["POST"])
def save_history():
    if not session.get("doctor_logged_in"):
        return redirect(url_for("doctor_login"))

    aadhaar = request.form.get("aadhaar")
    diagnosis = request.form.get("diagnosis")
    prescription = request.form.get("prescription")
    tests = request.form.get("tests")
    scan_token = request.form.get("scan_token")
    visit_date = datetime.today().strftime("%Y-%m-%d")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    doctor_name = session.get("doctor_name")
    
    # Save base history entry
    cur.execute("""
        INSERT INTO patient_history (aadhaar, visit_date, diagnosis, prescription, advised_tests, doctor_name, prescription_image, prescription_image_name)
        VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL)
    """, (aadhaar, visit_date, diagnosis, prescription, tests, doctor_name))
    
    cur.execute("SELECT LAST_INSERT_ID() as new_id")
    insert_row = cur.fetchone()
    history_id = insert_row["new_id"] if insert_row else cur.lastrowid

    if scan_token:
        # Retrieve all uploaded files in this session
        cur.execute("SELECT file_name, file_data FROM prescription_scan_session_files WHERE token = %s", (scan_token,))
        session_files = cur.fetchall()
        if session_files:
            # Set the first image on legacy column for backward compatibility
            legacy_name = session_files[0]["file_name"]
            legacy_data = session_files[0]["file_data"]
            cur.execute("""
                UPDATE patient_history 
                SET prescription_image = %s, prescription_image_name = %s
                WHERE history_id = %s
            """, (legacy_data, legacy_name, history_id))
            
            # Store all images in the normalized multi-table
            for sf in session_files:
                cur.execute("""
                    INSERT INTO patient_history_prescriptions (history_id, file_name, file_data)
                    VALUES (%s, %s, %s)
                """, (history_id, sf["file_name"], sf["file_data"]))
                
            # Clear temporary session
            cur.execute("DELETE FROM prescription_scan_sessions WHERE token = %s", (scan_token,))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for("doctor_dashboard"))

# -------------------- Download Lab Report --------------------
@app.route("/doctor/download_report/<int:report_id>")
def download_report(report_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_name, file_data FROM lab_reports WHERE id = %s", (report_id,))
    report = cur.fetchone()
    cur.close()

    if report:
        file_data = report[1]
        # Check if it is a Cloudinary URL
        if isinstance(file_data, str) and file_data.startswith("http"):
            return redirect(file_data)
        elif isinstance(file_data, bytes):
            try:
                decoded = file_data.decode("utf-8")
                if decoded.startswith("http"):
                    return redirect(decoded)
            except Exception:
                pass

        return send_file(BytesIO(file_data),
                         download_name=report[0],
                         as_attachment=True)

    return "Report not found", 404

# -------------------- View Lab Report Inline --------------------
@app.route("/doctor/view_report/<int:report_id>")
def view_report(report_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_name, file_data FROM lab_reports WHERE id = %s", (report_id,))
    report = cur.fetchone()
    cur.close()

    if report:
        file_name = report[0].lower()
        file_data = report[1]
        
        # Check if it is a Cloudinary URL
        if isinstance(file_data, str) and file_data.startswith("http"):
            return redirect(file_data)
        elif isinstance(file_data, bytes):
            try:
                decoded = file_data.decode("utf-8")
                if decoded.startswith("http"):
                    return redirect(decoded)
            except Exception:
                pass

        mimetype = "application/pdf"
        if file_name.endswith(".png"):
            mimetype = "image/png"
        elif file_name.endswith(".jpg") or file_name.endswith(".jpeg"):
            mimetype = "image/jpeg"
        elif file_name.endswith(".txt"):
            mimetype = "text/plain"
            
        return send_file(BytesIO(file_data),
                         mimetype=mimetype,
                         as_attachment=False)

    return "Report not found", 404

# -------------------- Doctor Logout --------------------
@app.route("/doctor/logout")
def doctor_logout():
    session.clear()
    return redirect(url_for("doctor_login"))

# -------------------- Lab Login --------------------
@app.route("/lab/login", methods=["GET", "POST"])
def lab_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM lab_staff WHERE username=%s AND password=%s", (username, password))
        lab_staff = cur.fetchone()
        cur.close()

        if lab_staff:
            session.pop("doctor_logged_in", None)
            session.pop("doctor_name", None)
            session.pop("receptionist_logged_in", None)
            session.pop("receptionist_name", None)
            session["lab_logged_in"] = True
            session["lab_id"] = lab_staff["lab_staff_id"]
            session["lab_name"] = lab_staff["name"]
            return redirect(url_for("lab_dashboard"))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for("lab_login"))

    return render_template("lab_login.html")

@app.route("/lab/dashboard", methods=["GET", "POST"])
def lab_dashboard():
    if not session.get("lab_logged_in"):
        return redirect(url_for("lab_login"))

    patient = None
    history = []
    reports = []
    aadhaar = None

    if request.method == "POST":
        aadhaar = request.form.get("aadhaar")

    if not aadhaar:
        aadhaar = request.args.get("aadhaar")

    # Fetch all uploaded reports to filter pending lists (with date and history_id)
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, aadhaar, report_type, report_date, history_id, uploaded_by FROM lab_reports")
    all_uploaded = cur.fetchall()
    
    # Organize uploaded tests by patient
    uploaded_by_aadhaar = {}
    for r in all_uploaded:
        p_aadhaar = r["aadhaar"]
        if p_aadhaar not in uploaded_by_aadhaar:
            uploaded_by_aadhaar[p_aadhaar] = []
        uploaded_by_aadhaar[p_aadhaar].append(r)

    is_locked_by_other = False
    locked_by_name = None

    if aadhaar:
        cur.execute("SELECT name, aadhaar, age, gender FROM patients WHERE aadhaar = %s", (aadhaar,))
        patient = cur.fetchone()
        
        if patient:
            # Get doctor-advised tests
            cur.execute("""
                SELECT history_id, visit_date, diagnosis, advised_tests, doctor_name, locked_by, locked_at 
                FROM patient_history WHERE aadhaar = %s 
                ORDER BY visit_date DESC
            """, (aadhaar,))
            history = cur.fetchall()

            # Check if any history record is locked by another staff (lock duration: 10 minutes)
            current_time = datetime.now()
            for h in history:
                l_by = h["locked_by"]
                l_at = h["locked_at"]
                if l_by and l_by != session.get("lab_name"):
                    if l_at and (current_time - l_at) < timedelta(minutes=10):
                        is_locked_by_other = True
                        locked_by_name = l_by
                        break

            # If not locked by another user, claim/update lock for current lab staff
            if not is_locked_by_other:
                for h in history:
                    if h["advised_tests"]:
                        cur.execute("""
                            UPDATE patient_history 
                            SET locked_by = %s, locked_at = NOW() 
                            WHERE history_id = %s
                        """, (session.get("lab_name"), h["history_id"]))
                mysql.connection.commit()

            # Extract individual tests that are paid but NOT uploaded yet
            cur.execute("""
                SELECT lr.report_type as name, lr.history_id, COALESCE(h.doctor_name, 'Doctor') as doctor_name
                FROM lab_reports lr
                LEFT JOIN patient_history h ON lr.history_id = h.history_id
                WHERE lr.aadhaar = %s AND lr.file_name = 'Pending Upload'
            """, (aadhaar,))
            advised_tests_list = cur.fetchall()

            # Get previously uploaded reports (fully completed)
            cur.execute("""
                SELECT id, report_date, report_type, uploaded_by 
                FROM lab_reports WHERE aadhaar = %s AND file_name != 'Pending Upload'
                ORDER BY report_date DESC, id DESC
            """, (aadhaar,))
            reports = cur.fetchall()
            
        cur.close()

    # Fetch pending tests for sidebar (candidates where payment is cleared but file is pending upload)
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT lr.history_id, p.name, p.aadhaar, lr.report_date as visit_date, 
               GROUP_CONCAT(lr.report_type SEPARATOR ', ') as advised_tests, 
               COALESCE(h.doctor_name, 'Doctor') as doctor_name, h.locked_by, h.locked_at
        FROM lab_reports lr
        JOIN patients p ON lr.aadhaar = p.aadhaar
        LEFT JOIN patient_history h ON lr.history_id = h.history_id
        WHERE lr.file_name = 'Pending Upload'
        GROUP BY lr.history_id, p.name, p.aadhaar, lr.report_date, h.doctor_name, h.locked_by, h.locked_at
        ORDER BY lr.report_date ASC
    """)
    pending_candidates = cur.fetchall()
    cur.close()

    # Filter out and format
    pending_tests = []
    current_time = datetime.now()
    for h in pending_candidates:
        l_by = h["locked_by"]
        l_at = h["locked_at"]
        
        # Check active lock
        is_active_lock = False
        if l_by and l_at and (current_time - l_at) < timedelta(minutes=10):
            is_active_lock = True
        
        h["is_locked"] = is_active_lock
        h["locked_by"] = l_by
        pending_tests.append(h)
        if len(pending_tests) >= 20:
            break

    today_date = date.today().strftime("%Y-%m-%d")
    return render_template("lab_dashboard.html",
                           patient=patient,
                           history=history,
                           reports=reports,
                           aadhaar=aadhaar,
                           today_date=today_date,
                           pending_tests=pending_tests,
                           is_locked_by_other=is_locked_by_other,
                           locked_by_name=locked_by_name,
                           advised_tests_list=advised_tests_list if aadhaar and patient else [])

@app.route("/lab/upload_report", methods=["POST"])
def lab_upload_report():
    if not session.get("lab_logged_in"):
        return redirect(url_for("lab_login"))

    aadhaar = request.form.get("aadhaar")
    uploaded_by = session.get("lab_name")

    # 1. Check if it is a single custom upload
    custom_type = request.form.get("custom_report_type")
    if custom_type:
        file = request.files.get("report_file")
        report_date = request.form.get("report_date")
        if file and file.filename != '':
            file_name = file.filename
            file_data = compress_image_data(file_name, file.read())

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO lab_reports (aadhaar, report_date, report_type, file_name, file_data, uploaded_by, history_id)
                VALUES (%s, %s, %s, %s, %s, %s, NULL)
            """, (aadhaar, report_date, custom_type, file_name, file_data, uploaded_by))
            mysql.connection.commit()
            cur.close()
            flash("Custom report uploaded successfully!", "success")
        else:
            flash("Failed to upload custom report. Please select a valid file.", "danger")
        return redirect(url_for("lab_dashboard", aadhaar=aadhaar))

    # 2. Otherwise, process bulk individual test uploads
    uploaded_count = 0
    cur = mysql.connection.cursor()

    for key in request.form:
        if key.startswith("report_type_"):
            index = key.split("_")[-1]
            report_type = request.form.get(key)
            report_date = request.form.get(f"report_date_{index}")
            history_id = request.form.get(f"history_id_{index}")
            file = request.files.get(f"report_file_{index}")

            if file and file.filename != '':
                file_name = file.filename
                file_data = compress_image_data(file_name, file.read())

                # Convert to integer if exists
                h_id = int(history_id) if history_id else None

                cur.execute("""
                    INSERT INTO lab_reports (aadhaar, report_date, report_type, file_name, file_data, uploaded_by, history_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (aadhaar, report_date, report_type, file_name, file_data, uploaded_by, h_id))
                uploaded_count += 1

    mysql.connection.commit()
    cur.close()

    if uploaded_count > 0:
        flash(f"Successfully uploaded {uploaded_count} lab report(s)!", "success")
    else:
        flash("No files were selected for upload.", "warning")

    return redirect(url_for("lab_dashboard", aadhaar=aadhaar))

@app.route("/api/lab/upload_report", methods=["POST"])
def api_lab_upload_report():
    if not session.get("lab_logged_in"):
        return {"error": "Unauthorized"}, 401

    aadhaar = request.form.get("aadhaar")
    report_type = request.form.get("report_type")
    report_date = request.form.get("report_date")
    history_id = request.form.get("history_id")
    file = request.files.get("report_file")
    uploaded_by = session.get("lab_name")

    if not file or file.filename == '':
        return {"error": "No file uploaded"}, 400

    file_name = file.filename
    file_bytes = file.read()
    
    # Compress if it's an image
    compressed_bytes = compress_image_data(file_name, file_bytes)
    
    # Upload to Cloudinary
    cloudinary_url = upload_to_cloudinary(file_name, compressed_bytes, folder="lab_reports")
    if not cloudinary_url:
        return {"error": "Failed to upload report to Cloudinary storage"}, 500

    h_id = int(history_id) if history_id else None

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Check if a paid pending upload row exists
    cur.execute("""
        SELECT id FROM lab_reports 
        WHERE history_id = %s AND report_type = %s AND file_name = 'Pending Upload'
    """, (h_id, report_type))
    pending_row = cur.fetchone()
    
    if pending_row:
        # Update the existing row with the file details
        cur.execute("""
            UPDATE lab_reports 
            SET file_name = %s, file_data = %s, report_date = %s, uploaded_by = %s
            WHERE id = %s
        """, (file_name, cloudinary_url, report_date, uploaded_by, pending_row["id"]))
    else:
        # Insert a new lab report row (standard route)
        cur.execute("""
            INSERT INTO lab_reports (aadhaar, report_date, report_type, file_name, file_data, uploaded_by, history_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (aadhaar, report_date, report_type, file_name, cloudinary_url, uploaded_by, h_id))
    
    # Release lock on successful upload
    if h_id:
        cur.execute("""
            UPDATE patient_history 
            SET locked_by = NULL, locked_at = NULL 
            WHERE history_id = %s
        """, (h_id,))
        
    mysql.connection.commit()
    cur.close()

    return {"success": True, "message": f"Successfully uploaded {report_type}!"}

@app.route("/api/search_tests")
def api_search_tests():
    query = request.args.get("query", "").strip()
    if not query:
        return {"tests": []}
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT test_name, price 
        FROM lab_test_catalog 
        WHERE LOWER(test_name) LIKE LOWER(%s) 
        LIMIT 10
    """, (f"%{query}%",))
    rows = cur.fetchall()
    cur.close()
    
    # Format decimal to float for JSON compatibility
    tests_list = []
    for r in rows:
        tests_list.append({
            "test_name": r["test_name"],
            "price": float(r["price"])
        })
    return {"tests": tests_list}

@app.route("/api/lab/pending_tests")
def api_lab_pending_tests():
    if not session.get("lab_logged_in"):
        return {"error": "Unauthorized"}, 401

    active_aadhaar = request.args.get("active_aadhaar")
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 1. Check lock of the active patient
    is_locked_by_other = False
    locked_by_name = None
    if active_aadhaar:
        cur.execute("""
            SELECT locked_by, locked_at FROM patient_history 
            WHERE aadhaar = %s ORDER BY visit_date DESC
        """, (active_aadhaar,))
        active_history = cur.fetchall()
        
        current_time = datetime.now()
        for h in active_history:
            l_by = h["locked_by"]
            l_at = h["locked_at"]
            if l_by and l_by != session.get("lab_name"):
                if l_at and (current_time - l_at) < timedelta(minutes=10):
                    is_locked_by_other = True
                    locked_by_name = l_by
                    break

    # 2. Fetch all pending tests for sidebar (candidates where payment is cleared but file is pending upload)
    cur.execute("""
        SELECT lr.history_id, p.name, p.aadhaar, lr.report_date as visit_date, 
               GROUP_CONCAT(lr.report_type SEPARATOR ', ') as advised_tests, 
               COALESCE(h.doctor_name, 'Doctor') as doctor_name, h.locked_by, h.locked_at
        FROM lab_reports lr
        JOIN patients p ON lr.aadhaar = p.aadhaar
        LEFT JOIN patient_history h ON lr.history_id = h.history_id
        WHERE lr.file_name = 'Pending Upload'
        GROUP BY lr.history_id, p.name, p.aadhaar, lr.report_date, h.doctor_name, h.locked_by, h.locked_at
        ORDER BY lr.report_date ASC
    """)
    pending_candidates = cur.fetchall()
    cur.close()

    pending_tests = []
    current_time = datetime.now()
    for h in pending_candidates:
        l_by = h["locked_by"]
        l_at = h["locked_at"]
        
        # Check active lock
        is_active_lock = False
        if l_by and l_at and (current_time - l_at) < timedelta(minutes=10):
            is_active_lock = True
        
        pending_tests.append({
            "history_id": h["history_id"],
            "name": h["name"],
            "aadhaar": h["aadhaar"],
            "visit_date": h["visit_date"].strftime("%Y-%m-%d"),
            "advised_tests": h["advised_tests"],
            "doctor_name": h["doctor_name"],
            "is_locked": is_active_lock,
            "locked_by": l_by
        })
        if len(pending_tests) >= 20:
            break

    return {
        "pending_tests": pending_tests,
        "is_locked_by_other": is_locked_by_other,
        "locked_by_name": locked_by_name
    }

@app.route("/lab/logout")
def lab_logout():
    session.clear()
    return redirect(url_for("lab_login"))

# -------------------- Patient Portal / Home Features --------------------
@app.route("/schedule")
def view_schedule():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT name, specialization FROM doctors ORDER BY specialization, name")
    doctors = cur.fetchall()
    cur.close()
    return render_template("doctor_schedule.html", doctors=doctors)

@app.route("/labreport", methods=["POST"])
def view_patient_reports():
    aadhaar = request.form.get("aadhar")
    patient = None
    reports = []

    if aadhaar:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT name, aadhaar FROM patients WHERE aadhaar = %s", (aadhaar,))
        patient = cur.fetchone()
        
        if patient:
            cur.execute("""
                SELECT id, report_date, report_type 
                FROM lab_reports WHERE aadhaar = %s 
                ORDER BY report_date DESC, id DESC
            """, (aadhaar,))
            reports = cur.fetchall()
            
        cur.close()

    return render_template("patient_reports.html", patient=patient, reports=reports)

# -------------------- Prescription Mobile Scan Features --------------------
import uuid
from io import BytesIO
from flask import send_file

@app.route("/api/prescription/request_token", methods=["POST"])
def api_request_token():
    token = str(uuid.uuid4())
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO prescription_scan_sessions (token, status, file_name, file_data)
        VALUES (%s, 'pending', NULL, NULL)
    """, (token,))
    mysql.connection.commit()
    cur.close()
    
    # Generate dynamic mobile link
    mobile_url = request.url_root.rstrip('/') + url_for('mobile_upload', token=token)
    return {"token": token, "mobile_url": mobile_url}

@app.route("/mobile/prescription/upload/<token>")
def mobile_upload(token):
    # Public route accessible by mobile devices
    return render_template("mobile_upload.html", token=token)

@app.route("/api/prescription/upload_mobile/<token>", methods=["POST"])
def api_upload_mobile(token):
    files = request.files.getlist("prescription_file")
    if not files or all(f.filename == "" for f in files):
        return "<h3>Error: No files uploaded</h3>", 400
        
    cur = mysql.connection.cursor()
    for file in files:
        if file.filename != "":
            file_name = file.filename
            file_data = file.read()
            # Upload to Cloudinary and get URL
            cloudinary_url = upload_to_cloudinary(file_name, file_data, folder="prescriptions")
            if cloudinary_url:
                cur.execute("""
                    INSERT INTO prescription_scan_session_files (token, file_name, file_data)
                    VALUES (%s, %s, %s)
                """, (token, file_name, cloudinary_url))
            
    cur.execute("""
        UPDATE prescription_scan_sessions 
        SET status = 'uploaded'
        WHERE token = %s
    """, (token,))
    mysql.connection.commit()
    cur.close()
    
    return """
        <div style='text-align: center; font-family: sans-serif; padding-top: 50px; color: #047857;'>
            <h2>✓ Successfully Synced!</h2>
            <p>All prescription pages have been sent to the doctor's screen. You can close this tab now.</p>
        </div>
    """

@app.route("/api/prescription/check_token/<token>")
def api_check_token(token):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT status FROM prescription_scan_sessions WHERE token = %s", (token,))
    session_data = cur.fetchone()
    if not session_data:
        cur.close()
        return {"error": "Token not found"}, 404
        
    if session_data["status"] == "uploaded":
        cur.execute("SELECT file_name FROM prescription_scan_session_files WHERE token = %s", (token,))
        files = cur.fetchall()
        file_names = [f["file_name"] for f in files]
        cur.close()
        return {"status": "uploaded", "file_name": ", ".join(file_names), "count": len(file_names)}
        
    cur.close()
    return session_data

@app.route("/doctor/prescription/raw_image/<int:history_id>")
def serve_prescription_raw_image(history_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT prescription_image_name, prescription_image FROM patient_history WHERE history_id = %s", (history_id,))
    data = cur.fetchone()
    cur.close()
    if data and data[1]:
        file_data = data[1]
        # Check if it is a Cloudinary URL
        if isinstance(file_data, str) and file_data.startswith("http"):
            return redirect(file_data)
        elif isinstance(file_data, bytes):
            try:
                decoded = file_data.decode("utf-8")
                if decoded.startswith("http"):
                    return redirect(decoded)
            except Exception:
                pass
        mimetype = "image/png"
        if data[0].lower().endswith(".jpg") or data[0].lower().endswith(".jpeg"):
            mimetype = "image/jpeg"
        return send_file(BytesIO(file_data), mimetype=mimetype, as_attachment=False)
    return "Prescription not found", 404

@app.route("/doctor/prescription/multi_raw_image/<int:file_id>")
def serve_prescription_multi_raw_image(file_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_name, file_data FROM patient_history_prescriptions WHERE id = %s", (file_id,))
    data = cur.fetchone()
    cur.close()
    if data and data[1]:
        file_data = data[1]
        # Check if it is a Cloudinary URL
        if isinstance(file_data, str) and file_data.startswith("http"):
            return redirect(file_data)
        elif isinstance(file_data, bytes):
            try:
                decoded = file_data.decode("utf-8")
                if decoded.startswith("http"):
                    return redirect(decoded)
            except Exception:
                pass
        mimetype = "image/png"
        if data[0].lower().endswith(".jpg") or data[0].lower().endswith(".jpeg"):
            mimetype = "image/jpeg"
        return send_file(BytesIO(file_data), mimetype=mimetype, as_attachment=False)
    return "File not found", 404

@app.route("/doctor/prescription/image/<int:history_id>")
def serve_prescription_image(history_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, file_name, file_data FROM patient_history_prescriptions WHERE history_id = %s", (history_id,))
    files = cur.fetchall()
    
    # Check if there is a single legacy image
    cur.execute("SELECT prescription_image_name, prescription_image FROM patient_history WHERE history_id = %s", (history_id,))
    legacy_data = cur.fetchone()
    cur.close()
    
    if not files:
        if legacy_data and legacy_data["prescription_image"]:
            img_src = legacy_data["prescription_image"] if legacy_data["prescription_image"].startswith("http") else f"/doctor/prescription/raw_image/{history_id}"
            return f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <style>
                    html, body {{
                        margin: 0;
                        padding: 0;
                        width: 100%;
                        height: 100%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        background-color: #0f172a;
                        overflow: hidden;
                    }}
                    img {{
                        max-width: 95%;
                        max-height: 95%;
                        object-fit: contain;
                        border-radius: 12px;
                        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                    }}
                </style>
            </head>
            <body>
                <img src="{img_src}" alt="Prescription Receipt">
            </body>
            </html>
            """
        return "Prescription not found", 404
        
    # Render multiple images in a vertically scrollable container
    img_tags = ""
    for f in files:
        img_src = f["file_data"] if f["file_data"].startswith("http") else f"/doctor/prescription/multi_raw_image/{f['id']}"
        img_tags += f'<div class="img-wrapper"><img src="{img_src}" alt="{f["file_name"]}"></div>\n'
        
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                background-color: #0f172a;
            }}
            .gallery-container {{
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 20px;
                padding: 20px;
                overflow-y: auto;
                height: calc(100% - 40px);
            }}
            .img-wrapper {{
                max-width: 95%;
                text-align: center;
            }}
            img {{
                max-width: 100%;
                height: auto;
                border-radius: 12px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
        </style>
    </head>
    <body>
        <div class="gallery-container">
            {img_tags}
        </div>
    </body>
    </html>
    """

@app.route("/other/login", methods=["GET", "POST"])
def other_login():
    role = request.args.get("role", "staff")
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Admin login credentials
        if role == "admin":
            if username == "admin" and password == "admin123":
                session.pop("doctor_logged_in", None)
                session.pop("lab_logged_in", None)
                session.pop("receptionist_logged_in", None)
                session["admin_logged_in"] = True
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid Admin credentials", "danger")
                return redirect(url_for("other_login", role=role))
                
        # Accounts Office login credentials
        if role == "accounts_office":
            if username == "accounts" and password == "pass123":
                session.pop("doctor_logged_in", None)
                session.pop("lab_logged_in", None)
                session.pop("receptionist_logged_in", None)
                session.pop("admin_logged_in", None)
                session["accounts_office_logged_in"] = True
                return redirect(url_for("accounts_office_dashboard"))
            else:
                flash("Invalid Accounts credentials", "danger")
                return redirect(url_for("other_login", role=role))
                
        # Other portals placeholder authentication
        if username == "other" and password == "pass123":
            role_name = role.replace("_", " ").title()
            return f"""
                <div style='text-align: center; font-family: sans-serif; padding-top: 100px; color: #064e3b; background: #f0fdf4; min-height: 100vh; margin: 0;'>
                    <span style='font-size: 4rem;'>🔓</span>
                    <h2 style='font-size: 2.2rem;'>Welcome to the {role_name} Portal!</h2>
                    <p style='color: #047857;'>The specialized dashboard is coming soon. Stay tuned!</p>
                    <br>
                    <a href='/admin/login' style='color: #10b981; font-weight: bold; text-decoration: none;'>&larr; Back to Gateways</a>
                </div>
            """
        flash("Invalid username or password", "danger")
        return redirect(url_for("other_login", role=role))
    return render_template("other_login.html")

# -------------------- System Admin Dashboard --------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("other_login", role="admin"))

    # Date range filters (default to today)
    today_str = date.today().isoformat()
    start_date = request.args.get("start_date", today_str)
    end_date = request.args.get("end_date", today_str)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 1. Total Patient Visits (Appointments)
    cur.execute("""
        SELECT COUNT(*) as count 
        FROM appointments 
        WHERE appointment_date BETWEEN %s AND %s
    """, (start_date, end_date))
    visits_count = cur.fetchone()["count"]

    # 2. Patients per Department
    cur.execute("""
        SELECT department, COUNT(*) as count 
        FROM appointments 
        WHERE appointment_date BETWEEN %s AND %s 
        GROUP BY department
    """, (start_date, end_date))
    queried_dept_stats = cur.fetchall()

    departments_list = [
        "General Medicine", "Cardiology", "Neurology", "Orthopedics",
        "Dermatology", "Pediatrics", "Gynecology & Obstetrics", "ENT",
        "Ophthalmology", "Psychiatry", "Pulmonology", "Gastroenterology",
        "Urology", "General Surgery", "Dentistry", "Physician"
    ]
    dept_map = {dept: 0 for dept in departments_list}
    for item in queried_dept_stats:
        dept_name = item["department"]
        if dept_name in dept_map:
            dept_map[dept_name] = item["count"]
        else:
            dept_map[dept_name] = item["count"] # Keep custom departments if any
            
    dept_stats = [{"department": k, "count": v} for k, v in dept_map.items()]

    # 3. Total Lab Tests done
    cur.execute("""
        SELECT COUNT(*) as count 
        FROM lab_reports 
        WHERE report_date BETWEEN %s AND %s
    """, (start_date, end_date))
    tests_count = cur.fetchone()["count"]

    # 4. Total Sales & Payment Methods breakdown
    cur.execute("""
        SELECT payment_method, SUM(COALESCE(amount, 0.00)) as total 
        FROM appointments 
        WHERE appointment_date BETWEEN %s AND %s 
        GROUP BY payment_method
    """, (start_date, end_date))
    appt_sales = cur.fetchall()

    cur.execute("""
        SELECT payment_method, SUM(COALESCE(amount, 0.00)) as total 
        FROM lab_reports 
        WHERE report_date BETWEEN %s AND %s 
        GROUP BY payment_method
    """, (start_date, end_date))
    lab_sales = cur.fetchall()

    # Merge payments
    sales_by_method = {"Cash": 0.0, "UPI": 0.0, "Card": 0.0}
    for s in appt_sales:
        method = s["payment_method"]
        if method in sales_by_method:
            total_val = s["total"]
            sales_by_method[method] += float(total_val) if total_val is not None else 0.0
            
    for s in lab_sales:
        method = s["payment_method"]
        if method in sales_by_method:
            total_val = s["total"]
            sales_by_method[method] += float(total_val) if total_val is not None else 0.0

    total_sales = sum(sales_by_method.values())

    # 5. Detailed Transactions List
    cur.execute("""
        SELECT 'Appointment' as type, p.name as patient_name, a.department as details, 
               COALESCE(a.amount, 0.00) as amount, a.payment_method, a.appointment_date as txn_date 
        FROM appointments a 
        JOIN patients p ON a.aadhaar = p.aadhaar 
        WHERE a.appointment_date BETWEEN %s AND %s
    """, (start_date, end_date))
    appt_txns = cur.fetchall()

    cur.execute("""
        SELECT 'Lab Test' as type, p.name as patient_name, l.report_type as details, 
               COALESCE(l.amount, 0.00) as amount, l.payment_method, l.report_date as txn_date 
        FROM lab_reports l 
        JOIN patients p ON l.aadhaar = p.aadhaar 
        WHERE l.report_date BETWEEN %s AND %s
    """, (start_date, end_date))
    lab_txns = cur.fetchall()

    cur.close()

    # Combine and sort transactions by date descending
    all_txns = appt_txns + lab_txns
    all_txns.sort(key=lambda x: x["txn_date"], reverse=True)

    return render_template("admin_dashboard.html",
                           start_date=start_date,
                           end_date=end_date,
                           visits_count=visits_count,
                           dept_stats=dept_stats,
                           tests_count=tests_count,
                           sales_by_method=sales_by_method,
                           total_sales=total_sales,
                           all_txns=all_txns)

# -------------------- Accounts Office Dashboard --------------------
@app.route("/accounts_office/dashboard")
def accounts_office_dashboard():
    if not session.get("accounts_office_logged_in"):
        return redirect(url_for("other_login", role="accounts_office"))

    today_str = date.today().isoformat()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 1. Total collections today by Cash, UPI, Card
    cur.execute("""
        SELECT payment_method, SUM(COALESCE(amount, 0.00)) as total 
        FROM appointments 
        WHERE appointment_date = %s 
        GROUP BY payment_method
    """, (today_str,))
    appt_sales = cur.fetchall()

    cur.execute("""
        SELECT payment_method, SUM(COALESCE(amount, 0.00)) as total 
        FROM lab_reports 
        WHERE report_date = %s 
        GROUP BY payment_method
    """, (today_str,))
    lab_sales = cur.fetchall()

    sales_by_method = {"Cash": 0.0, "UPI": 0.0, "Card": 0.0}
    for s in appt_sales:
        method = s["payment_method"]
        if method in sales_by_method:
            total_val = s["total"]
            sales_by_method[method] += float(total_val) if total_val is not None else 0.0
            
    for s in lab_sales:
        method = s["payment_method"]
        if method in sales_by_method:
            total_val = s["total"]
            sales_by_method[method] += float(total_val) if total_val is not None else 0.0

    today_total = sum(sales_by_method.values())

    # 2. Detailed transactions log for today
    cur.execute("""
        SELECT 'Appointment' as type, p.name as patient_name, a.department as details, 
               COALESCE(a.amount, 0.00) as amount, a.payment_method, a.appointment_date as txn_date 
        FROM appointments a 
        JOIN patients p ON a.aadhaar = p.aadhaar 
        WHERE a.appointment_date = %s
    """, (today_str,))
    appt_txns = cur.fetchall()

    cur.execute("""
        SELECT 'Lab Test' as type, p.name as patient_name, l.report_type as details, 
               COALESCE(l.amount, 0.00) as amount, l.payment_method, l.report_date as txn_date 
        FROM lab_reports l 
        JOIN patients p ON l.aadhaar = p.aadhaar 
        WHERE l.report_date = %s
    """, (today_str,))
    lab_txns = cur.fetchall()

    all_txns = appt_txns + lab_txns
    all_txns.sort(key=lambda x: x["txn_date"], reverse=True)

    # 3. Patient billing search
    search_aadhaar = request.args.get("search_aadhaar")
    patient = None
    pending_tests = []
    
    if search_aadhaar:
        cur.execute("SELECT name, aadhaar, age, gender FROM patients WHERE aadhaar = %s", (search_aadhaar,))
        patient = cur.fetchone()
        
        if patient:
            # Get clinical history for advised tests
            cur.execute("""
                SELECT history_id, advised_tests, visit_date, doctor_name 
                FROM patient_history 
                WHERE aadhaar = %s AND advised_tests IS NOT NULL AND advised_tests != ''
            """, (search_aadhaar,))
            history_records = cur.fetchall()
            
            # Get already billed/uploaded reports for this patient
            cur.execute("SELECT report_type, history_id, file_name FROM lab_reports WHERE aadhaar = %s", (search_aadhaar,))
            billed_reports = cur.fetchall()
            
            # Map history_id and report_type to see if already billed
            billed_set = set()
            for r in billed_reports:
                billed_set.add((r["history_id"], r["report_type"].lower().strip()))

            # Fetch catalog prices for fast lookups
            cur.execute("SELECT test_name, price FROM lab_test_catalog")
            catalog_rows = cur.fetchall()
            price_map = {row["test_name"].lower().strip(): float(row["price"]) for row in catalog_rows}
                
            for h in history_records:
                h_id = h["history_id"]
                advised = [t.strip() for t in h["advised_tests"].split(",") if t.strip()]
                for test_name in advised:
                    if (h_id, test_name.lower()) not in billed_set:
                        # Default to 350.00 if test name not matched in DB catalog
                        matched_price = price_map.get(test_name.lower().strip(), 350.00)
                        pending_tests.append({
                            "history_id": h_id,
                            "test_name": test_name,
                            "price": matched_price,
                            "visit_date": h["visit_date"].strftime("%Y-%m-%d"),
                            "doctor_name": h["doctor_name"]
                        })

    cur.close()

    return render_template("accounts_office_dashboard.html",
                           today_total=today_total,
                           sales_by_method=sales_by_method,
                           all_txns=all_txns,
                           patient=patient,
                           pending_tests=pending_tests,
                           search_aadhaar=search_aadhaar)

# -------------------- Collect Payment & Authorize Lab Test --------------------
@app.route("/accounts_office/collect_payment", methods=["POST"])
def collect_payment():
    if not session.get("accounts_office_logged_in"):
        return {"error": "Unauthorized"}, 401

    aadhaar = request.form.get("aadhaar")
    history_id = request.form.get("history_id")
    test_name = request.form.get("test_name")
    amount = request.form.get("amount", "350.00")
    payment_method = request.form.get("payment_method", "UPI")
    today_str = date.today().isoformat()

    cur = mysql.connection.cursor()
    
    # Insert placeholder entry into lab_reports indicating paid but pending file upload
    cur.execute("""
        INSERT INTO lab_reports (aadhaar, report_date, report_type, file_name, file_data, uploaded_by, history_id, amount, payment_method)
        VALUES (%s, %s, %s, 'Pending Upload', 'Pending Upload', 'Accounts Office', %s, %s, %s)
    """, (aadhaar, today_str, test_name, int(history_id), amount, payment_method))
    
    mysql.connection.commit()
    cur.close()

    flash(f"Payment of ₹{float(amount):,.2f} for {test_name} processed successfully! Lab test authorized.", "success")
    return redirect(url_for("accounts_office_dashboard", search_aadhaar=aadhaar))

# -------------------- Accounts Office Logout --------------------
@app.route("/accounts_office/logout")
def accounts_office_logout():
    session.pop("accounts_office_logged_in", None)
    return redirect(url_for("admin_login"))

if __name__ == "__main__":
    app.run(debug=True)

