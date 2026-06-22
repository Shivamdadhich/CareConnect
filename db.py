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

    def _create_connection(self):
        host = os.getenv("DB_HOST", "localhost")
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASS", "")
        database = os.getenv("DB_NAME", "patient_details")
        port = int(os.getenv("DB_PORT", 3306))
        
        # Setup SSL if specified (recommended/required for cloud DBs)
        ssl_mode = os.getenv("DB_SSL_MODE", "False").lower() in ("true", "1", "yes")
        ssl_config = {"min_version": "TLSv1.2"} if ssl_mode else None

        return pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            ssl=ssl_config,
            autocommit=True  # set autocommit=True to ensure inserts/updates are visible immediately
        )

    @property
    def connection(self):
        # Reuse a global/instance-level connection to leverage serverless warm container reuse.
        # This completely avoids reconnecting on every request when the container is warm.
        if self._conn is None or not self._conn.open:
            self._conn = self._create_connection()
        else:
            try:
                # Ping the connection and reconnect if it went away
                self._conn.ping(reconnect=True)
            except Exception:
                self._conn = self._create_connection()
        return self._conn

mysql_instance = None

def get_connection(app=None):
    global mysql_instance
    if mysql_instance is None:
        mysql_instance = MySQLWrapper(app)
    return mysql_instance
