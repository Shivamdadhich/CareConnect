import sys
import os
from dotenv import load_dotenv
import pymysql

# Load env configurations
sys.path.append("c:/Users/Owner/OneDrive/Desktop/CareConnect 2.0")
load_dotenv()

def seed_missing_doctors():
    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASS", "")
    database = os.getenv("DB_NAME", "patient_details")
    port = int(os.getenv("DB_PORT", 3306))
    
    ssl_mode = os.getenv("DB_SSL_MODE", "False").lower() in ("true", "1", "yes")
    ssl_config = {} if ssl_mode else None

    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        ssl=ssl_config,
        autocommit=True
    )
    cursor = conn.cursor()
    
    # Target departments list
    departments = [
        "General Medicine",
        "Cardiology",
        "Neurology",
        "Orthopedics",
        "Dermatology",
        "Pediatrics",
        "Gynecology & Obstetrics",
        "ENT",
        "Ophthalmology",
        "Psychiatry",
        "Pulmonology",
        "Gastroenterology",
        "Urology",
        "General Surgery",
        "Dentistry"
    ]
    
    # 2 Doctors per department (Indian names)
    doctors_data = {
        "General Medicine": [
            ("amit.sharma", "Dr. Amit Sharma"),
            ("priya.patel", "Dr. Priya Patel")
        ],
        "Cardiology": [
            ("rajesh.khanna", "Dr. Rajesh Khanna"),
            ("deepak.mehta", "Dr. Deepak Mehta")
        ],
        "Neurology": [
            ("sanjay.dutt", "Dr. Sanjay Dutt"),
            ("aruna.roy", "Dr. Aruna Roy")
        ],
        "Orthopedics": [
            ("anil.kapoor", "Dr. Anil Kapoor"),
            ("sunita.rao", "Dr. Sunita Rao")
        ],
        "Dermatology": [
            ("kabir.sen", "Dr. Kabir Sen"),
            ("neha.gupta", "Dr. Neha Gupta")
        ],
        "Pediatrics": [
            ("sneha.reddy", "Dr. Sneha Reddy"),
            ("vikram.malhotra", "Dr. Vikram Malhotra")
        ],
        "Gynecology & Obstetrics": [
            ("meera.nair", "Dr. Meera Nair"),
            ("rohan.joshi", "Dr. Rohan Joshi")
        ],
        "ENT": [
            ("alok.pathak", "Dr. Alok Pathak"),
            ("divya.singh", "Dr. Divya Singh")
        ],
        "Ophthalmology": [
            ("vijay.mallya", "Dr. Vijay Mallya"),
            ("kiran.shaw", "Dr. Kiran Shaw")
        ],
        "Psychiatry": [
            ("anupam.kher", "Dr. Anupam Kher"),
            ("shalini.srivastava", "Dr. Shalini Srivastava")
        ],
        "Pulmonology": [
            ("rahul.bajaj", "Dr. Rahul Bajaj"),
            ("pooja.hegde", "Dr. Pooja Hegde")
        ],
        "Gastroenterology": [
            ("aditya.roy", "Dr. Aditya Roy"),
            ("richa.chaddha", "Dr. Richa Chaddha")
        ],
        "Urology": [
            ("manish.pandey", "Dr. Manish Pandey"),
            ("kavita.krishnamurthy", "Dr. Kavita Krishnamurthy")
        ],
        "General Surgery": [
            ("suresh.raina", "Dr. Suresh Raina"),
            ("monika.sharma", "Dr. Monika Sharma")
        ],
        "Dentistry": [
            ("harish.rawat", "Dr. Harish Rawat"),
            ("tanvi.azmi", "Dr. Tanvi Azmi")
        ],
        "Physician": [
            ("sandeep.sharma", "Dr. Sandeep Sharma"),
            ("neha.deshmukh", "Dr. Neha Deshmukh"),
            ("aravind.swamy", "Dr. Aravind Swamy"),
            ("kavya.nair", "Dr. Kavya Nair")
        ]
    }
    
    print("Deleting old generic seed entries to prevent conflict...")
    cursor.execute("DELETE FROM doctors WHERE username IN ('doctor1', 'doctor2')")
    
    print("Inserting/Updating doctors...")
    for dept, docs in doctors_data.items():
        for username, name in docs:
            cursor.execute("""
                INSERT INTO doctors (username, password, name, specialization)
                VALUES (%s, 'pass123', %s, %s)
                ON DUPLICATE KEY UPDATE name=VALUES(name), specialization=VALUES(specialization)
            """, (username, name, dept))
            
    conn.commit()
    cursor.close()
    conn.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_missing_doctors()
