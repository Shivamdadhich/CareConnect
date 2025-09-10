from flask import Flask, render_template, request, redirect, url_for, send_file
from db import get_connection
from datetime import date, datetime, timedelta
from io import BytesIO
from fpdf import FPDF

app = Flask(__name__)
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
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "receptionist" and password == "pass123":
            return redirect(url_for("receptionist_dashboard"))
        error = "Invalid username or password."
    return render_template("receptionist_login.html", error=error)


@app.route("/receptionist/dashboard")
def receptionist_dashboard():
    return render_template("receptionist_dashboard.html")


# -------------------- Search Patient --------------------
@app.route("/receptionist/search", methods=["GET", "POST"])
def search_patient():
    if request.method == "POST":
        aadhaar = request.form.get("aadhaar")
        cursor = None
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT * FROM patients WHERE aadhaar = %s", (aadhaar,))
            patient = cursor.fetchone()
        except Exception as e:
            print("Error fetching patient:", e)
            patient = None
        finally:
            if cursor:
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

        cursor = None
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO patients (aadhaar, name, age, gender, contact, address)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (aadhaar, name, age, gender, phone, address))
            mysql.connection.commit()
        except Exception as e:
            print("Error inserting patient:", e)
            mysql.connection.rollback()
            return f"Error inserting patient: {e}"
        finally:
            if cursor:
                cursor.close()

        return redirect(url_for("make_appointment", aadhaar=aadhaar))

    aadhaar = request.args.get("aadhaar")
    return render_template("register_patient.html", aadhaar=aadhaar)


# -------------------- Make Appointment --------------------
@app.route("/receptionist/appointment", methods=["GET", "POST"])
def make_appointment():
    cursor = None
    if request.method == "POST":
        aadhaar = request.form.get("aadhaar")
        department = request.form.get("department")
        doctor = request.form.get("doctor")
        appointment_date = request.form.get("date")

        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT name, age, gender FROM patients WHERE aadhaar = %s", (aadhaar,))
            patient = cursor.fetchone()

            if not patient:
                return f"Error: No patient found with Aadhaar {aadhaar}"

            name = patient['name']
            age = patient['age']
            gender = patient['gender']

            cursor.execute("""
                INSERT INTO appointments (aadhaar, department, doctor, appointment_date)
                VALUES (%s, %s, %s, %s)
            """, (aadhaar, department, doctor, appointment_date))
            mysql.connection.commit()
        except Exception as e:
            print("Failed to book appointment:", e)
            mysql.connection.rollback()
            return f"Failed to book appointment: {e}"
        finally:
            if cursor:
                cursor.close()

        return redirect(url_for("appointment_confirmation",
                                uhid=aadhaar,
                                name=name,
                                age=age,
                                gender=gender,
                                department=department,
                                doctor=doctor,
                                appointment_date=appointment_date))

    aadhaar = request.args.get("aadhaar")
    min_date = date.today().isoformat()
    return render_template("make_appointment.html", aadhaar=aadhaar, min_date=min_date)


# -------------------- Appointment Confirmation --------------------
@app.route("/receptionist/appointment/confirmation")
def appointment_confirmation():
    uhid = request.args.get("uhid")
    name = request.args.get("name")
    age = request.args.get("age")
    gender = request.args.get("gender")
    department = request.args.get("department")
    doctor = request.args.get("doctor")
    appointment_date = request.args.get("appointment_date")

    appointment_datetime = datetime.strptime(appointment_date, '%Y-%m-%d')
    valid_upto = (appointment_datetime + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    amount = "0.00"

    return render_template("appointment_confirmation.html",
                           uhid=uhid, name=name, age=age, gender=gender,
                           department=department, doctor=doctor,
                           appointment_date=appointment_date,
                           valid_upto=valid_upto, amount=amount)


# -------------------- Generate PDF Receipt --------------------
@app.route("/receptionist/appointment/receipt")
def generate_pdf():
    uhid = request.args.get("uhid")
    name = request.args.get("name")
    age = request.args.get("age")
    gender = request.args.get("gender")
    department = request.args.get("department")
    doctor = request.args.get("doctor")
    appointment_date = request.args.get("appointment_date")

    if not all([uhid, name, age, gender, department, doctor, appointment_date]):
        return "Error: Missing required data for PDF generation."

    appointment_datetime = datetime.strptime(appointment_date, '%Y-%m-%d')
    valid_upto = (appointment_datetime + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    amount = "₹0.00"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Appointment Receipt", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", size=12)
    left_col = [f"UHID: {uhid}", f"Name: {name}", f"Age: {age}", f"Gender: {gender}", f"Amount: {amount}"]
    right_col = [f"Department: {department}", f"Doctor: {doctor}", f"Appointment Date: {appointment_date}", f"Valid Upto: {valid_upto}"]

    start_y = pdf.get_y()
    left_x, right_x = 10, 110
    line_height = 10

    for i, text in enumerate(left_col):
        pdf.set_xy(left_x, start_y + i * line_height)
        pdf.cell(90, line_height, text)

    for i, text in enumerate(right_col):
        pdf.set_xy(right_x, start_y + i * line_height)
        pdf.cell(90, line_height, text)

    pdf.ln(20)
    pdf.set_y(start_y + len(left_col) * line_height + 20)
    pdf.set_font("Arial", "I", 12)
    pdf.cell(0, 10, "Doctor's Notes / Prescription:")
    pdf.ln(40)

    pdf_output = BytesIO()
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    pdf_output.write(pdf_bytes)
    pdf_output.seek(0)

    return send_file(pdf_output, as_attachment=True, download_name=f"appointment_{uhid}.pdf")


# -------------------- Doctor Login --------------------
@app.route("/doctor/login", methods=["GET", "POST"])
def doctor_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "doctor" and password == "pass123":
            return redirect(url_for("doctor_dashboard"))
        return "<h3>Invalid credentials. <a href='/doctor/login'>Try again</a></h3>"
    return render_template("doctor_login.html")


@app.route("/doctor/dashboard")
def doctor_dashboard():
    return render_template("doctor_dashboard.html")


# -------------------- Doctor Patient History --------------------
@app.route("/doctor/patient-history", methods=["GET", "POST"])
def doctor_patient_history():
    patient = None
    history = None
    error = None
    if request.method == "POST":
        aadhaar = request.form.get("aadhaar")
        cursor = None
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT * FROM patients WHERE aadhaar = %s", (aadhaar,))
            patient = cursor.fetchone()
            cursor.execute("SELECT * FROM patient_history WHERE aadhaar = %s", (aadhaar,))
            history = cursor.fetchall()
        except Exception as e:
            print("Error fetching patient history:", e)
            patient = None
            history = None
        finally:
            if cursor:
                cursor.close()
        if not patient:
            error = "Patient not found"

    return render_template("access_patient_history.html", patient=patient, history=history, error=error)


# -------------------- Doctor Lab Reports --------------------
@app.route("/doctor/lab-reports", methods=["GET", "POST"])
def doctor_lab_reports():
    patient = None
    lab_reports = None
    error = None
    if request.method == "POST":
        aadhaar = request.form.get("aadhaar")
        cursor = None
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT * FROM patients WHERE aadhaar = %s", (aadhaar,))
            patient = cursor.fetchone()
            cursor.execute("SELECT * FROM lab_reports WHERE aadhaar = %s", (aadhaar,))
            lab_reports = cursor.fetchall()
        except Exception as e:
            print("Error fetching lab reports:", e)
            patient = None
            lab_reports = None
        finally:
            if cursor:
                cursor.close()
        if not patient:
            error = "Patient not found"

    return render_template("access_lab_reports.html", patient=patient, lab_reports=lab_reports, error=error)


# -------------------- Lab Login --------------------
@app.route("/lab/login", methods=["GET", "POST"])
def lab_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "lab" and password == "pass123":
            return "<h3>Welcome Lab In-Charge! (Dashboard coming soon)</h3>"
        return "<h3>Invalid credentials. <a href='/lab/login'>Try again</a></h3>"
    return render_template("lab_login.html")


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
