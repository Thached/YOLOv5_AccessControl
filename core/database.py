"""
SQLite数据库模块
- 用户表(users): 账号密码与权限
- 人脸特征表(face_features): 注册人脸的特征向量
- 通行记录表(access_records): 每次识别的详细记录
- 系统设置表(settings): key-value 配置项
"""
import os
import sqlite3
import hashlib
import pickle
import datetime
import threading
import numpy as np


DB_PATH = 'data/access_control.db'

DDL_STATEMENTS = [
    '''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''',
    '''CREATE TABLE IF NOT EXISTS face_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        feature_data BLOB NOT NULL,
        image_count INTEGER DEFAULT 20,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''',
    '''CREATE TABLE IF NOT EXISTS access_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        name TEXT,
        result TEXT NOT NULL,
        confidence REAL DEFAULT 0,
        temperature REAL,
        distance REAL,
        image BLOB,
        timestamp TEXT DEFAULT (datetime('now','localtime'))
    )''',
    '''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''',
]

DEFAULT_SETTINGS = {
    'detect_method': 'yolov5',
    'model_name': 'yolov5su',
    'confidence_threshold': '0.5',
    'recognition_threshold': '70',
    'temp_limit': '37.2',
    'dist_min': '10',
    'dist_max': '120',
    'auto_interval': '3',
    'gate_delay': '3',
    'retry_limit': '5',
    'lockout_duration': '5',
    'stranger_snapshot': 'true',
    'model_path': './model/model.xml',
    'onnx_model_path': './model/yolov5s.onnx',
}


class Database:
    """SQLite 数据库管理类（线程安全）"""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        self._init_default_settings()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            for stmt in DDL_STATEMENTS:
                conn.execute(stmt)
            conn.commit()
            conn.close()

    def _init_default_settings(self):
        for key, val in DEFAULT_SETTINGS.items():
            if self.get_setting(key) is None:
                self.set_setting(key, val)

    # ========== 用户管理 ==========

    @staticmethod
    def _hash_pwd(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def add_user(self, username, password, role='user'):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    'INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
                    (username, self._hash_pwd(password), role))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def verify_user(self, username, password):
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                'SELECT * FROM users WHERE username=? AND password_hash=?',
                (username, self._hash_pwd(password))).fetchone()
            conn.close()
            return dict(row) if row else None

    def delete_user(self, username):
        if username == 'admin':
            return False
        with self._lock:
            conn = self._get_conn()
            conn.execute('DELETE FROM users WHERE username=?', (username,))
            conn.execute('DELETE FROM face_features WHERE name=?', (username,))
            conn.commit()
            conn.close()
            return True

    def get_all_users(self):
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute('SELECT username, role, created_at FROM users').fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def user_exists(self, username):
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                'SELECT id FROM users WHERE username=?', (username,)).fetchone()
            conn.close()
            return row is not None

    # ========== 人脸特征管理 ==========

    def save_face_features(self, name, features, image_count=20):
        """保存人脸特征向量（LBPH直方图等）"""
        with self._lock:
            conn = self._get_conn()
            user_row = conn.execute(
                'SELECT id FROM users WHERE username=?', (name,)).fetchone()
            user_id = user_row['id'] if user_row else 0
            blob = pickle.dumps(features)
            existing = conn.execute(
                'SELECT id FROM face_features WHERE name=?', (name,)).fetchone()
            if existing:
                conn.execute(
                    'UPDATE face_features SET feature_data=?, image_count=? WHERE name=?',
                    (blob, image_count, name))
            else:
                conn.execute(
                    'INSERT INTO face_features (user_id, name, feature_data, image_count) VALUES (?,?,?,?)',
                    (user_id, name, blob, image_count))
            conn.commit()
            conn.close()

    def load_face_features(self, name=None):
        """加载人脸特征向量"""
        with self._lock:
            conn = self._get_conn()
            if name:
                row = conn.execute(
                    'SELECT * FROM face_features WHERE name=?', (name,)).fetchone()
                conn.close()
                if row:
                    d = dict(row)
                    d['feature_data'] = pickle.loads(d['feature_data'])
                    return d
                return None
            rows = conn.execute('SELECT * FROM face_features').fetchall()
            conn.close()
            result = {}
            for r in rows:
                d = dict(r)
                d['feature_data'] = pickle.loads(d['feature_data'])
                result[d['name']] = d
            return result

    def delete_face_features(self, name):
        with self._lock:
            conn = self._get_conn()
            conn.execute('DELETE FROM face_features WHERE name=?', (name,))
            conn.commit()
            conn.close()

    def get_all_face_names(self):
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute('SELECT name FROM face_features').fetchall()
            conn.close()
            return [r['name'] for r in rows]

    # ========== 通行记录 ==========

    def add_access_record(self, username, name, result, confidence=0,
                          temperature=None, distance=None, image=None):
        """添加通行记录"""
        with self._lock:
            conn = self._get_conn()
            user_row = conn.execute(
                'SELECT id FROM users WHERE username=?', (username,)).fetchone()
            user_id = user_row['id'] if user_row else 0
            img_blob = None
            if image is not None:
                import cv2
                _, buf = cv2.imencode('.jpg', image)
                img_blob = buf.tobytes()
            conn.execute(
                '''INSERT INTO access_records
                   (user_id, username, name, result, confidence, temperature, distance, image)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (user_id, username, name, result, confidence, temperature, distance, img_blob))
            conn.commit()
            conn.close()

    def query_records(self, date_from=None, date_to=None, username=None,
                      result=None, limit=500):
        """查询通行记录"""
        with self._lock:
            conn = self._get_conn()
            sql = 'SELECT id, username, name, result, confidence, temperature, distance, timestamp FROM access_records WHERE 1=1'
            params = []
            if date_from:
                sql += ' AND timestamp >= ?'
                params.append(date_from)
            if date_to:
                sql += ' AND timestamp <= ?'
                params.append(date_to)
            if username:
                sql += ' AND username LIKE ?'
                params.append(f'%{username}%')
            if result:
                sql += ' AND result = ?'
                params.append(result)
            sql += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_record_image(self, record_id):
        """获取某条记录的抓拍图像"""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                'SELECT image FROM access_records WHERE id=?', (record_id,)).fetchone()
            conn.close()
            if row and row['image']:
                img_array = np.frombuffer(row['image'], dtype=np.uint8)
                return img_array
            return None

    def get_statistics(self):
        """获取统计信息"""
        with self._lock:
            conn = self._get_conn()
            total = conn.execute('SELECT COUNT(*) as cnt FROM access_records').fetchone()['cnt']
            success = conn.execute(
                "SELECT COUNT(*) as cnt FROM access_records WHERE result='success'").fetchone()['cnt']
            fail = conn.execute(
                "SELECT COUNT(*) as cnt FROM access_records WHERE result='fail'").fetchone()['cnt']
            today = conn.execute(
                "SELECT COUNT(*) as cnt FROM access_records WHERE date(timestamp)=date('now','localtime')"
            ).fetchone()['cnt']
            conn.close()
            return {'total': total, 'success': success, 'fail': fail, 'today': today}

    # ========== 系统设置 ==========

    def get_setting(self, key):
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                'SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            conn.close()
            return row['value'] if row else None

    def set_setting(self, key, value):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                'INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)',
                (key, str(value)))
            conn.commit()
            conn.close()

    def get_all_settings(self):
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute('SELECT key, value FROM settings').fetchall()
            conn.close()
            return {r['key']: r['value'] for r in rows}

    def get_setting_float(self, key, default=0.0):
        try:
            return float(self.get_setting(key))
        except (TypeError, ValueError):
            return default

    def get_setting_int(self, key, default=0):
        try:
            return int(self.get_setting(key))
        except (TypeError, ValueError):
            return default

    def get_setting_bool(self, key, default=False):
        val = self.get_setting(key)
        if val is None:
            return default
        return val.lower() in ('true', '1', 'yes')
