import os
import sys
import pymysql
from dotenv import load_dotenv

# Load env variables
load_dotenv()

def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASS", "")
    database = os.getenv("DB_NAME", "patient_details")
    port = int(os.getenv("DB_PORT", 3306))
    ssl_mode = os.getenv("DB_SSL_MODE", "False").lower() in ("true", "1", "yes")
    ssl_config = {} if ssl_mode else None

    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        ssl=ssl_config,
        autocommit=True
    )

def list_users():
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    print("\n--- RECEPTIONISTS ---")
    cursor.execute("SELECT name, username FROM receptionists")
    for row in cursor.fetchall():
        print(f"Name: {row['name']} | Username: {row['username']}")

    print("\n--- LAB STAFF ---")
    cursor.execute("SELECT name, username FROM lab_staff")
    for row in cursor.fetchall():
        print(f"Name: {row['name']} | Username: {row['username']}")

    print("\n--- DOCTORS ---")
    cursor.execute("SELECT name, username, specialization FROM doctors")
    for row in cursor.fetchall():
        print(f"Name: {row['name']} | Username: {row['username']} | Specialization: {row['specialization']}")
    
    print()
    cursor.close()
    conn.close()

def add_user(role, name, username, password, spec=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if role == "receptionist":
        query = "INSERT INTO receptionists (name, username, password) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name)"
        cursor.execute(query, (name, username, password))
        print(f"Successfully added/updated Receptionist: {name} ({username})")
    elif role == "lab":
        query = "INSERT INTO lab_staff (name, username, password) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name)"
        cursor.execute(query, (name, username, password))
        print(f"Successfully added/updated Lab Staff: {name} ({username})")
    elif role == "doctor":
        if not spec:
            print("Error: Specialization is required for a doctor!")
            return
        query = "INSERT INTO doctors (name, username, password, specialization) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name), specialization=VALUES(specialization)"
        cursor.execute(query, (name, username, password, spec))
        print(f"Successfully added/updated Doctor: {name} ({username}) | Specialization: {spec}")
    else:
        print("Invalid role! Choose: receptionist, lab, or doctor")

    cursor.close()
    conn.close()

def remove_user(role, username):
    conn = get_db_connection()
    cursor = conn.cursor()

    if role == "receptionist":
        cursor.execute("DELETE FROM receptionists WHERE username = %s", (username,))
        print(f"Removed receptionist with username: {username}")
    elif role == "lab":
        cursor.execute("DELETE FROM lab_staff WHERE username = %s", (username,))
        print(f"Removed lab staff member with username: {username}")
    elif role == "doctor":
        cursor.execute("DELETE FROM doctors WHERE username = %s", (username,))
        print(f"Removed doctor with username: {username}")
    else:
        print("Invalid role! Choose: receptionist, lab, or doctor")

    cursor.close()
    conn.close()

def print_help():
    print("""
CareConnect DB Management Tool
-------------------------------
Usage:
  python db_tool.py list
  python db_tool.py add [receptionist|lab|doctor] "Name" "username" "password" ["specialization"]
  python db_tool.py remove [receptionist|lab|doctor] "username"
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "list":
        list_users()
    elif cmd == "add":
        if len(sys.argv) < 6:
            if len(sys.argv) == 5 and sys.argv[2].lower() != "doctor":
                # Valid for receptionist / lab
                add_user(sys.argv[2].lower(), sys.argv[3], sys.argv[4], sys.argv[5])
            else:
                print("Missing arguments for adding user!")
                print_help()
        else:
            spec = sys.argv[6] if len(sys.argv) > 6 else None
            add_user(sys.argv[2].lower(), sys.argv[3], sys.argv[4], sys.argv[5], spec)
    elif cmd == "remove":
        if len(sys.argv) < 4:
            print("Missing arguments for removing user!")
            print_help()
        else:
            remove_user(sys.argv[2].lower(), sys.argv[3])
    else:
        print_help()
