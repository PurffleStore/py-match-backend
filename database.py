# database.py
import hashlib
import json
import urllib.parse
from typing import Dict

import pyodbc
from flask import Flask
from sqlalchemy import text

from config import (
    APP_ENV,
    DB_TYPE,
    SQL_DRIVER,
    SQL_SERVER,
    SQL_DB,
    SQL_TRUSTED,
    SQL_USER,
    SQL_PASSWORD,
    SQL_PORT,
    SQL_ENCRYPT,
    SQL_TRUSTCERT,
)
from models import db


def get_db_connection():
    """
    Raw DB connection.
    local       -> SQL Server (pyodbc)
    production  -> not used for MySQL paths
    """
    if DB_TYPE == "sqlserver":
        server = SQL_SERVER
        if SQL_PORT:
            server = f"{SQL_SERVER},{SQL_PORT}"

        if SQL_TRUSTED == "yes":
            conn_str = (
                f"DRIVER={{{SQL_DRIVER}}};"
                f"SERVER={server};"
                f"DATABASE={SQL_DB};"
                f"Trusted_Connection=yes;"
            )
        else:
            conn_str = (
                f"DRIVER={{{SQL_DRIVER}}};"
                f"SERVER={server};"
                f"DATABASE={SQL_DB};"
                f"UID={SQL_USER};"
                f"PWD={SQL_PASSWORD};"
            )

        if SQL_ENCRYPT == "yes":
            conn_str += "Encrypt=yes;"
        if SQL_TRUSTCERT == "yes":
            conn_str += "TrustServerCertificate=yes;"

        return pyodbc.connect(conn_str)

    raise RuntimeError("Raw pyodbc connection is supported only for local SQL Server mode")


def row_to_dict(cursor, row) -> Dict:
    if row is None:
        return {}
    cols = [col[0] for col in cursor.description]
    return {cols[i]: row[i] for i in range(len(cols))}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_database(app: Flask):
    """Initialize database connection for Flask app"""

    if DB_TYPE == "mysql":
        # Hostinger MySQL for production
        encoded_password = urllib.parse.quote_plus(SQL_PASSWORD)
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{SQL_USER}:{encoded_password}"
            f"@{SQL_SERVER}:{SQL_PORT}/{SQL_DB}"
        )
        print(f"🟢 Using MySQL database in {APP_ENV}: {SQL_SERVER}:{SQL_PORT}/{SQL_DB}")

    else:
        # Local SQL Server
        server = SQL_SERVER
        if SQL_PORT:
            server = f"{SQL_SERVER},{SQL_PORT}"

        if SQL_TRUSTED == "yes":
            raw = (
                f"DRIVER={{{SQL_DRIVER}}};"
                f"SERVER={server};"
                f"DATABASE={SQL_DB};"
                f"Trusted_Connection=yes;"
            )
        else:
            raw = (
                f"DRIVER={{{SQL_DRIVER}}};"
                f"SERVER={server};"
                f"DATABASE={SQL_DB};"
                f"UID={SQL_USER};"
                f"PWD={SQL_PASSWORD};"
            )

        if SQL_ENCRYPT == "yes":
            raw += "Encrypt=yes;"
        if SQL_TRUSTCERT == "yes":
            raw += "TrustServerCertificate=yes;"

        params = urllib.parse.quote_plus(raw)
        SQLALCHEMY_DATABASE_URI = f"mssql+pyodbc:///?odbc_connect={params}"
        print(f"🟢 Using SQL Server database in {APP_ENV}: {SQL_SERVER}/{SQL_DB}")

    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    db.init_app(app)

    # optional test connection
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Database connection test successful")
        except Exception as e:
            print(f"❌ Database connection test failed: {e}")
            raise

    return db


def fetch_profile_for_role(user_id: str, role: str) -> Dict:
    """
    Raw helper kept only for local SQL Server mode.
    Avoid using this in production MySQL mode.
    """
    if DB_TYPE != "sqlserver":
        raise RuntimeError("fetch_profile_for_role raw query is only supported in local SQL Server mode")

    table = {
        "marriage": "Marriage",
        "interview": "Interview",
        "partnership": "Partnership",
    }.get(role.lower())

    if not table:
        return {}

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT TOP 1 *
            FROM {table}
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {}

        prof = row_to_dict(cur, row)

        if "hobbies_interests" in prof and isinstance(prof["hobbies_interests"], str):
            if prof["hobbies_interests"].strip().startswith("["):
                try:
                    prof["hobbies_interests"] = json.loads(prof["hobbies_interests"])
                except Exception:
                    prof["hobbies_interests"] = [
                        s.strip()
                        for s in prof["hobbies_interests"].split(",")
                        if s.strip()
                    ]
            else:
                prof["hobbies_interests"] = [
                    s.strip()
                    for s in prof["hobbies_interests"].split(",")
                    if s.strip()
                ]

        prof["user_id"] = str(user_id)
        return prof

    except Exception as e:
        print("Profile fetch error:", e)
        return {}
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def fetch_expectation_data(user_id: str) -> Dict:
    """
    Use SQLAlchemy-compatible access for both environments.
    This avoids SQL Server-only raw connections in production.
    """
    from models import ExpectationResponse

    try:
        row = ExpectationResponse.query.filter_by(user_id=user_id) \
            .order_by(ExpectationResponse.created_at.desc()) \
            .first()

        if row is None:
            return {}

        result = {}
        for column in ExpectationResponse.__table__.columns:
            value = getattr(row, column.name)
            result[column.name] = value

        return result

    except Exception as e:
        print(f"Error fetching expectation data: {e}")
        return {}


def fetch_marriage_profile_data(user_id: str) -> Dict:
    """
    Use SQLAlchemy-compatible access for both environments.
    This avoids SQL Server-only raw connections in production.
    """
    from models import Marriage

    try:
        row = Marriage.query.filter_by(user_id=user_id) \
            .order_by(Marriage.created_at.desc()) \
            .first()

        if row is None:
            return {}

        result = {}
        for column in Marriage.__table__.columns:
            value = getattr(row, column.name)
            result[column.name] = value

        return result

    except Exception as e:
        print(f"Error fetching marriage profile data: {e}")
        return {}