-- Database Schema for CareConnect
-- Use this script to initialize your MySQL / Cloud database tables.

CREATE TABLE IF NOT EXISTS patients (
    aadhaar VARCHAR(12) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age INT,
    gender VARCHAR(20),
    contact VARCHAR(20),
    address TEXT
);

CREATE TABLE IF NOT EXISTS receptionists (
    receptionist_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS doctors (
    doctor_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    specialization VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_staff (
    lab_staff_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    aadhaar VARCHAR(12) NOT NULL,
    department VARCHAR(100) NOT NULL,
    doctor VARCHAR(100) NOT NULL,
    appointment_date DATE NOT NULL,
    FOREIGN KEY (aadhaar) REFERENCES patients(aadhaar) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS patient_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    aadhaar VARCHAR(12) NOT NULL,
    visit_date DATE NOT NULL,
    diagnosis TEXT NOT NULL,
    prescription TEXT,
    advised_tests TEXT,
    doctor_name VARCHAR(100),
    locked_by VARCHAR(100) DEFAULT NULL,
    locked_at DATETIME DEFAULT NULL,
    FOREIGN KEY (aadhaar) REFERENCES patients(aadhaar) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    aadhaar VARCHAR(12) NOT NULL,
    report_date DATE NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_data LONGBLOB NOT NULL,
    uploaded_by VARCHAR(100),
    history_id INT,
    FOREIGN KEY (aadhaar) REFERENCES patients(aadhaar) ON DELETE CASCADE,
    FOREIGN KEY (history_id) REFERENCES patient_history(history_id) ON DELETE SET NULL
);

-- Seed Initial Test Data
INSERT INTO receptionists (username, password, name) VALUES
('receptionist1', 'pass123', 'Alice Smith'),
('priya.sharma', 'pass123', 'Priya Sharma'),
('anjali.gupta', 'pass123', 'Anjali Gupta'),
('rohan.verma', 'pass123', 'Rohan Verma')
ON DUPLICATE KEY UPDATE name=VALUES(name);

INSERT INTO lab_staff (username, password, name) VALUES
('lab1', 'pass123', 'Jane Green'),
('amit.patel', 'pass123', 'Amit Patel'),
('sandeep.reddy', 'pass123', 'Sandeep Reddy'),
('vikas.mishra', 'pass123', 'Vikas Mishra'),
('neha.joshi', 'pass123', 'Neha Joshi'),
('sunita.rao', 'pass123', 'Sunita Rao')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Seed unique doctors across standard departments (2 doctors per department, Indian names only)
INSERT INTO doctors (username, password, name, specialization) VALUES
('amit.sharma', 'pass123', 'Dr. Amit Sharma', 'General Medicine'),
('priya.patel', 'pass123', 'Dr. Priya Patel', 'General Medicine'),
('rajesh.khanna', 'pass123', 'Dr. Rajesh Khanna', 'Cardiology'),
('deepak.mehta', 'pass123', 'Dr. Deepak Mehta', 'Cardiology'),
('sanjay.dutt', 'pass123', 'Dr. Sanjay Dutt', 'Neurology'),
('aruna.roy', 'pass123', 'Dr. Aruna Roy', 'Neurology'),
('anil.kapoor', 'pass123', 'Dr. Anil Kapoor', 'Orthopedics'),
('sunita.rao', 'pass123', 'Dr. Sunita Rao', 'Orthopedics'),
('kabir.sen', 'pass123', 'Dr. Kabir Sen', 'Dermatology'),
('neha.gupta', 'pass123', 'Dr. Neha Gupta', 'Dermatology'),
('sneha.reddy', 'pass123', 'Dr. Sneha Reddy', 'Pediatrics'),
('vikram.malhotra', 'pass123', 'Dr. Vikram Malhotra', 'Pediatrics'),
('meera.nair', 'pass123', 'Dr. Meera Nair', 'Gynecology & Obstetrics'),
('rohan.joshi', 'pass123', 'Dr. Rohan Joshi', 'Gynecology & Obstetrics'),
('alok.pathak', 'pass123', 'Dr. Alok Pathak', 'ENT'),
('divya.singh', 'pass123', 'Dr. Divya Singh', 'ENT'),
('vijay.mallya', 'pass123', 'Dr. Vijay Mallya', 'Ophthalmology'),
('kiran.shaw', 'pass123', 'Dr. Kiran Shaw', 'Ophthalmology'),
('anupam.kher', 'pass123', 'Dr. Anupam Kher', 'Psychiatry'),
('shalini.srivastava', 'pass123', 'Dr. Shalini Srivastava', 'Psychiatry'),
('rahul.bajaj', 'pass123', 'Dr. Rahul Bajaj', 'Pulmonology'),
('pooja.hegde', 'pass123', 'Dr. Pooja Hegde', 'Pulmonology'),
('aditya.roy', 'pass123', 'Dr. Aditya Roy', 'Gastroenterology'),
('richa.chaddha', 'pass123', 'Dr. Richa Chaddha', 'Gastroenterology'),
('manish.pandey', 'pass123', 'Dr. Manish Pandey', 'Urology'),
('kavita.krishnamurthy', 'pass123', 'Dr. Kavita Krishnamurthy', 'Urology'),
('suresh.raina', 'pass123', 'Dr. Suresh Raina', 'General Surgery'),
('monika.sharma', 'pass123', 'Dr. Monika Sharma', 'General Surgery'),
('harish.rawat', 'pass123', 'Dr. Harish Rawat', 'Dentistry'),
('tanvi.azmi', 'pass123', 'Dr. Tanvi Azmi', 'Dentistry'),
('sandeep.sharma', 'pass123', 'Dr. Sandeep Sharma', 'Physician'),
('neha.deshmukh', 'pass123', 'Dr. Neha Deshmukh', 'Physician'),
('aravind.swamy', 'pass123', 'Dr. Aravind Swamy', 'Physician'),
('kavya.nair', 'pass123', 'Dr. Kavya Nair', 'Physician')
ON DUPLICATE KEY UPDATE name=VALUES(name), specialization=VALUES(specialization);
