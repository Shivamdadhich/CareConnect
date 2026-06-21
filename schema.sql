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
INSERT INTO receptionists (username, password, name) 
VALUES ('receptionist1', 'pass123', 'Alice Smith')
ON DUPLICATE KEY UPDATE name=name;

INSERT INTO lab_staff (username, password, name) 
VALUES ('lab1', 'pass123', 'Jane Green')
ON DUPLICATE KEY UPDATE name=name;

-- Seed unique doctors across standard departments (2 doctors per department)
INSERT INTO doctors (username, password, name, specialization) VALUES
('doctor1', 'pass123', 'Dr. John Doe', 'Cardiology'),
('rajesh.khanna', 'pass123', 'Dr. Rajesh Khanna', 'Cardiology'),
('amit.sharma', 'pass123', 'Dr. Amit Sharma', 'General Medicine'),
('priya.patel', 'pass123', 'Dr. Priya Patel', 'General Medicine'),
('sneha.reddy', 'pass123', 'Dr. Sneha Reddy', 'Pediatrics'),
('vikram.malhotra', 'pass123', 'Dr. Vikram Malhotra', 'Pediatrics'),
('anil.kapoor', 'pass123', 'Dr. Anil Kapoor', 'Orthopedics'),
('sunita.williams', 'pass123', 'Dr. Sunita Williams', 'Orthopedics'),
('kabir.sen', 'pass123', 'Dr. Kabir Sen', 'Dermatology'),
('neha.gupta', 'pass123', 'Dr. Neha Gupta', 'Dermatology'),
('sanjay.dutt', 'pass123', 'Dr. Sanjay Dutt', 'Neurology'),
('aruna.roy', 'pass123', 'Dr. Aruna Roy', 'Neurology'),
('vijay.mallya', 'pass123', 'Dr. Vijay Mallya', 'Ophthalmology'),
('kiran.shaw', 'pass123', 'Dr. Kiran Shaw', 'Ophthalmology'),
('meera.nair', 'pass123', 'Dr. Meera Nair', 'Gynecology'),
('rohan.joshi', 'pass123', 'Dr. Rohan Joshi', 'Gynecology')
ON DUPLICATE KEY UPDATE name=VALUES(name), specialization=VALUES(specialization);
