import os
from flask_mysqldb import MySQL
from dotenv import load_dotenv

load_dotenv()

mysql = None  # global MySQL object

def get_connection(app=None):
    global mysql
    if mysql is None:
        if app is None:
            raise ValueError("First call to get_connection() must pass the Flask app")
        # Initialize MySQL with app
        app.config['MYSQL_HOST'] = os.getenv("DB_HOST", "localhost")
        app.config['MYSQL_USER'] = os.getenv("DB_USER", "root")
        app.config['MYSQL_PASSWORD'] = os.getenv("DB_PASS", "")
        app.config['MYSQL_DB'] = os.getenv("DB_NAME", "patient_details")
        app.config['MYSQL_PORT'] = int(os.getenv("DB_PORT", 3306))
        app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
        mysql = MySQL(app)
    return mysql
