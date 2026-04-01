# db.py
from config import (
    APP_ENV,
    LOCAL_SQL_DRIVER,
    LOCAL_SQL_SERVER,
    LOCAL_SQL_DB,
    LOCAL_SQL_TRUSTED,
    LOCAL_SQL_USER,
    LOCAL_SQL_PASSWORD,
    LOCAL_SQL_PORT,
    LOCAL_SQL_ENCRYPT,
    LOCAL_SQL_TRUST_CERT,
    PROD_MYSQL_HOST,
    PROD_MYSQL_PORT,
    PROD_MYSQL_DB,
    PROD_MYSQL_USER,
    PROD_MYSQL_PASSWORD,
)

def get_db_connection():
    if APP_ENV == "local":
        import pyodbc

        server_value = LOCAL_SQL_SERVER
        if LOCAL_SQL_PORT:
            server_value = f"{LOCAL_SQL_SERVER},{LOCAL_SQL_PORT}"

        if LOCAL_SQL_TRUSTED == "yes":
            conn_str = (
                f"DRIVER={{{LOCAL_SQL_DRIVER}}};"
                f"SERVER={server_value};"
                f"DATABASE={LOCAL_SQL_DB};"
                f"Trusted_Connection=yes;"
                f"Encrypt={LOCAL_SQL_ENCRYPT};"
                f"TrustServerCertificate={LOCAL_SQL_TRUST_CERT};"
            )
        else:
            conn_str = (
                f"DRIVER={{{LOCAL_SQL_DRIVER}}};"
                f"SERVER={server_value};"
                f"DATABASE={LOCAL_SQL_DB};"
                f"UID={LOCAL_SQL_USER};"
                f"PWD={LOCAL_SQL_PASSWORD};"
                f"Encrypt={LOCAL_SQL_ENCRYPT};"
                f"TrustServerCertificate={LOCAL_SQL_TRUST_CERT};"
            )

        return pyodbc.connect(conn_str)

    else:
        import pymysql

        return pymysql.connect(
            host=PROD_MYSQL_HOST,
            port=PROD_MYSQL_PORT,
            user=PROD_MYSQL_USER,
            password=PROD_MYSQL_PASSWORD,
            database=PROD_MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )