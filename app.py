from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from db import get_connection
from datetime import date, datetime, timedelta
from io import BytesIO
from fpdf import FPDF
import MySQLdb
import MySQLdb.cursors


app = Flask(__name__)
app.secret_key = "supersecretkey"

mysql = get_connection(app)

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
        appointment_date = request.form.get("date")

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT name, age, gender FROM patients WHERE aadhaar = %s", (aadhaar,))
        patient = cursor.fetchone()

        if not patient:
            return f"Error: No patient found with Aadhaar {aadhaar}"

        cursor.execute("""
            INSERT INTO appointments (aadhaar, department, doctor, appointment_date)
            VALUES (%s, %s, %s, %s)
        """, (aadhaar, department, doctor, appointment_date))
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
                               amount="0.00")

    aadhaar = request.args.get("aadhaar")
    min_date = date.today().isoformat()
    return render_template("make_appointment.html", aadhaar=aadhaar, min_date=min_date)

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
                SELECT visit_date, diagnosis, prescription, advised_tests
                FROM patient_history WHERE aadhaar = %s
                ORDER BY visit_date DESC
            """, (aadhaar,))
            history = [
                {"visit_date": h[0], "diagnosis": h[1], "prescription": h[2], "advised_tests": h[3]}
                for h in cur.fetchall()
            ]

            cur.execute("""
                SELECT id, report_date, report_type
                FROM lab_reports WHERE aadhaar = %s
                ORDER BY report_date DESC
            """, (aadhaar,))
            reports = [
                {"id": r[0], "report_date": r[1], "report_type": r[2]}
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
    visit_date = datetime.today().strftime("%Y-%m-%d")

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO patient_history (aadhaar, visit_date, diagnosis, prescription, advised_tests)
        VALUES (%s, %s, %s, %s, %s)
    """, (aadhaar, visit_date, diagnosis, prescription, tests))
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
        return send_file(BytesIO(report[1]),
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
        mimetype = "application/pdf"
        if file_name.endswith(".png"):
            mimetype = "image/png"
        elif file_name.endswith(".jpg") or file_name.endswith(".jpeg"):
            mimetype = "image/jpeg"
        elif file_name.endswith(".txt"):
            mimetype = "text/plain"
            
        return send_file(BytesIO(report[1]),
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

    if aadhaar:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT name, aadhaar, age, gender FROM patients WHERE aadhaar = %s", (aadhaar,))
        patient = cur.fetchone()
        
        if patient:
            # Get doctor-advised tests
            cur.execute("""
                SELECT visit_date, diagnosis, advised_tests 
                FROM patient_history WHERE aadhaar = %s 
                ORDER BY visit_date DESC
            """, (aadhaar,))
            history = cur.fetchall()

            # Extract individual tests
            advised_tests_list = []
            seen_tests = set()
            for h in history:
                if h["advised_tests"]:
                    parts = h["advised_tests"].split(",")
                    for part in parts:
                        test_name = part.strip()
                        if test_name and test_name.lower() not in seen_tests:
                            seen_tests.add(test_name.lower())
                            advised_tests_list.append(test_name)

            # Get previously uploaded reports
            cur.execute("""
                SELECT id, report_date, report_type 
                FROM lab_reports WHERE aadhaar = %s 
                ORDER BY report_date DESC
            """, (aadhaar,))
            reports = cur.fetchall()
            
        cur.close()

    # Fetch oldest 20 pending tests
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT p.name, p.aadhaar, h.visit_date, h.advised_tests
        FROM patient_history h
        JOIN patients p ON h.aadhaar = p.aadhaar
        WHERE h.advised_tests IS NOT NULL AND h.advised_tests != ''
        ORDER BY h.visit_date ASC
        LIMIT 20
    """)
    pending_tests = cur.fetchall()
    cur.close()

    today_date = date.today().strftime("%Y-%m-%d")
    return render_template("lab_dashboard.html",
                           patient=patient,
                           history=history,
                           reports=reports,
                           aadhaar=aadhaar,
                           today_date=today_date,
                           pending_tests=pending_tests,
                           advised_tests_list=advised_tests_list if aadhaar and patient else [])

@app.route("/lab/upload_report", methods=["POST"])
def lab_upload_report():
    if not session.get("lab_logged_in"):
        return redirect(url_for("lab_login"))

    aadhaar = request.form.get("aadhaar")

    # 1. Check if it is a single custom upload
    custom_type = request.form.get("custom_report_type")
    if custom_type:
        file = request.files.get("report_file")
        report_date = request.form.get("report_date")
        if file and file.filename != '':
            file_name = file.filename
            file_data = file.read()

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO lab_reports (aadhaar, report_date, report_type, file_name, file_data)
                VALUES (%s, %s, %s, %s, %s)
            """, (aadhaar, report_date, custom_type, file_name, file_data))
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
            file = request.files.get(f"report_file_{index}")

            if file and file.filename != '':
                file_name = file.filename
                file_data = file.read()

                cur.execute("""
                    INSERT INTO lab_reports (aadhaar, report_date, report_type, file_name, file_data)
                    VALUES (%s, %s, %s, %s, %s)
                """, (aadhaar, report_date, report_type, file_name, file_data))
                uploaded_count += 1

    mysql.connection.commit()
    cur.close()

    if uploaded_count > 0:
        flash(f"Successfully uploaded {uploaded_count} lab report(s)!", "success")
    else:
        flash("No files were selected for upload.", "warning")

    return redirect(url_for("lab_dashboard", aadhaar=aadhaar))

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
                ORDER BY report_date DESC
            """, (aadhaar,))
            reports = cur.fetchall()
            
        cur.close()

    return render_template("patient_reports.html", patient=patient, reports=reports)

# -------------------- Other Staff Login --------------------
@app.route("/other/login", methods=["GET", "POST"])
def other_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "other" and password == "pass123":
            return "<h3>Welcome Staff! (Dashboard coming soon)</h3>"
        return "<h3>Invalid credentials. <a href='/other/login'>Try again</a></h3>"
    return render_template("other_login.html")

if __name__ == "__main__":
    app.run(debug=True)

