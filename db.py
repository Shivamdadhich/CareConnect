import os
import sys
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from queue import Queue, Empty
import threading

# Inject pymysql as MySQLdb for compatibility with any existing imports
sys.modules['MySQLdb'] = pymysql
sys.modules['MySQLdb.cursors'] = pymysql.cursors

load_dotenv()

class SimpleConnectionPool:
    def __init__(self, creator, mincached=5, maxcached=30):
        self.creator = creator
        self.mincached = mincached
        self.maxcached = maxcached
        self.pool = Queue(maxsize=maxcached)
        self.lock = threading.Lock()
        self.active_conns = 0
        
        # Pre-populate pool
        for _ in range(mincached):
            try:
                conn = creator()
                self.pool.put(conn)
                self.active_conns += 1
            except Exception:
                pass

    def get_connection(self):
        # Clean up any closed connections from the pool
        while True:
            try:
                conn = self.pool.get_nowait()
                # Check if connection is still alive
                try:
                    conn.ping(reconnect=True)
                    return conn
                except Exception:
                    # Connection is dead, try to create a new one
                    with self.lock:
                        self.active_conns -= 1
                    continue
            except Empty:
                break
        
        # Pool is empty, create a new connection if under maxcached
        with self.lock:
            if self.active_conns < self.maxcached:
                try:
                    conn = self.creator()
                    self.active_conns += 1
                    return conn
                except Exception:
                    pass
        
        # If we reached max cached and pool is empty, block/wait for one
        try:
            conn = self.pool.get(timeout=10) # wait up to 10 seconds
            try:
                conn.ping(reconnect=True)
                return conn
            except Exception:
                with self.lock:
                    self.active_conns -= 1
                return self.get_connection()
        except Empty:
            raise Exception("Timeout waiting for database connection from pool")

    def release_connection(self, conn):
        try:
            self.pool.put_nowait(conn)
        except Exception:
            # Pool is full, close this connection
            try:
                conn.close()
            except Exception:
                pass
            with self.lock:
                self.active_conns -= 1

class MySQLWrapper:
    def __init__(self, app=None):
        self.app = app
        self._conn = None
        self.pool = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        @app.teardown_appcontext
        def teardown_db(exception):
            from flask import g
            conn = g.pop('db_conn', None)
            if conn is not None and self.pool is not None:
                self.pool.release_connection(conn)

    def _create_connection(self):
        host = os.getenv("DB_HOST", "localhost")
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASS", "")
        database = os.getenv("DB_NAME", "careconnect")
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
            autocommit=True
        )

    def _get_pool(self):
        if self.pool is None:
            self.pool = SimpleConnectionPool(self._create_connection, mincached=5, maxcached=30)
        return self.pool

    @property
    def connection(self):
        from flask import has_request_context, g
        if has_request_context():
            if 'db_conn' not in g:
                g.db_conn = self._get_pool().get_connection()
            return g.db_conn
        else:
            # Fallback for CLI/scripts
            if self._conn is None or not self._conn.open:
                self._conn = self._create_connection()
            return self._conn

mysql_instance = None

def get_connection(app=None):
    global mysql_instance
    if mysql_instance is None:
        mysql_instance = MySQLWrapper(app)
    elif app is not None and mysql_instance.app is None:
        mysql_instance.init_app(app)
    return mysql_instance

