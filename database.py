# database.py
import pyodbc
import urllib.parse
import hashlib
import json
import pickle
import random
from typing import Dict, List
from flask import Flask
from config import SQL_DRIVER, SQL_SERVER, SQL_DB, SQL_TRUSTED, SQL_USER, SQL_PASSWORD, SQL_PORT, SQL_ENCRYPT, SQL_TRUSTCERT
from models import db

def get_db_connection():
    """Get a raw pyodbc connection"""
    return pyodbc.connect(
        f"DRIVER={SQL_DRIVER};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DB};"
        f"Trusted_Connection={SQL_TRUSTED};"
    )

def row_to_dict(cursor, row) -> Dict:
    """Convert a database row to dictionary"""
    if row is None:
        return {}
    cols = [col[0] for col in cursor.description]
    return {cols[i]: row[i] for i in range(len(cols))}

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_database(app: Flask):
    """Initialize database connection for Flask app"""
    _server = SQL_SERVER
    if SQL_PORT:
        _server = f"{SQL_SERVER},{SQL_PORT}"

    if SQL_TRUSTED == "yes":
        raw = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={_server};"
            f"DATABASE={SQL_DB};"
            f"Trusted_Connection=yes;"
        )
    else:
        raw = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={_server};"
            f"DATABASE={SQL_DB};"
            f"UID={SQL_USER};PWD={SQL_PASSWORD};"
        )

    if SQL_ENCRYPT == "yes":
        raw += "Encrypt=yes;"
    if SQL_TRUSTCERT == "yes":
        raw += "TrustServerCertificate=yes;"

    params = urllib.parse.quote_plus(raw)
    SQLALCHEMY_DATABASE_URI = f"mssql+pyodbc:///?odbc_connect={params}"

    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    db.init_app(app)
    
    return db

def fetch_profile_for_role(user_id: str, role: str) -> Dict:
    """Fetch profile from the correct table based on role"""
    table = {
        "marriage": "Marriage",
        "interview": "Interview",
        "partnership": "Partnership"
    }.get(role.lower())

    if not table:
        return {}

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT TOP 1 *
            FROM {table}
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        row = cur.fetchone()
        if row is None:
            return {}
        prof = row_to_dict(cur, row)
        # Normalize hobbies_interests if it exists
        if "hobbies_interests" in prof and isinstance(prof["hobbies_interests"], str):
            if prof["hobbies_interests"].strip().startswith("["):
                try:
                    prof["hobbies_interests"] = json.loads(prof["hobbies_interests"])
                except Exception:
                    prof["hobbies_interests"] = [s.strip() for s in prof["hobbies_interests"].split(",") if s.strip()]
            else:
                prof["hobbies_interests"] = [s.strip() for s in prof["hobbies_interests"].split(",") if s.strip()]
        prof["user_id"] = str(user_id)
        return prof
    except pyodbc.Error as e:
        print("Profile fetch error:", e)
        return {}
    finally:
        try: conn.close()
        except: pass

def fetch_expectation_data(user_id: str) -> Dict:
    """Fetch expectation data from ExpectationResponse table"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM ExpectationResponse
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        row = cur.fetchone()
        if row is None:
            return {}
        return row_to_dict(cur, row)
    except Exception as e:
        print(f"Error fetching expectation data: {e}")
        return {}
    finally:
        try: conn.close()
        except: pass

def fetch_marriage_profile_data(user_id: str) -> Dict:
    """Fetch marriage profile data for comparison"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM Marriage
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        row = cur.fetchone()
        if row is None:
            return {}
        return row_to_dict(cur, row)
    except Exception as e:
        print(f"Error fetching marriage profile data: {e}")
        return {}
    finally:
        try: conn.close()
        except: pass