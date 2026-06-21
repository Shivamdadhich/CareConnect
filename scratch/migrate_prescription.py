import sys
import os
from dotenv import load_dotenv
import pymysql

sys.path.append("c:/Users/Owner/OneDrive/Desktop/CareConnect 2.0")
load_dotenv()

def apply_migration():
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
    
    print("Modifying patient_history table structure...")
    try:
        cursor.execute("ALTER TABLE patient_history ADD COLUMN prescription_image LONGBLOB DEFAULT NULL")
    except Exception as e:
        print("Column prescription_image might already exist:", e)

    try:
        cursor.execute("ALTER TABLE patient_history ADD COLUMN prescription_image_name VARCHAR(255) DEFAULT NULL")
    except Exception as e:
        print("Column prescription_image_name might already exist:", e)

    print("Creating prescription_scan_sessions table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prescription_scan_sessions (
            token VARCHAR(100) PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            file_name VARCHAR(255) DEFAULT NULL,
            file_data LONGBLOB DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Database migrations applied successfully!")

if __name__ == "__main__":
    apply_migration()
