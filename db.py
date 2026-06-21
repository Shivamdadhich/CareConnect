import os
import sys
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

# Inject pymysql as MySQLdb for compatibility with any existing imports
sys.modules['MySQLdb'] = pymysql
sys.modules['MySQLdb.cursors'] = pymysql.cursors

load_dotenv()

class MySQLWrapper:
    def __init__(self, app=None):
        self.app = app
        self._conn = None

    @property
    def connection(self):
        # Establish connection if not already open
        if self._conn is None or not self._conn.open:
            host = os.getenv("DB_HOST", "localhost")
            user = os.getenv("DB_USER", "root")
            password = os.getenv("DB_PASS", "")
            database = os.getenv("DB_NAME", "patient_details")
            port = int(os.getenv("DB_PORT", 3306))
            
            # Setup SSL if specified (recommended/required for cloud DBs)
            ssl_mode = os.getenv("DB_SSL_MODE", "False").lower() in ("true", "1", "yes")
            ssl_config = {} if ssl_mode else None

            self._conn = pymysql.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                port=port,
                ssl=ssl_config,
                autocommit=True  # set autocommit=True to ensure inserts/updates are visible immediately
            )
        return self._conn

mysql_instance = None

def get_connection(app=None):
    global mysql_instance
    if mysql_instance is None:
        mysql_instance = MySQLWrapper(app)
    return mysql_instance
