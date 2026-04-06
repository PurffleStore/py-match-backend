# config.py
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load local .env file
load_dotenv(os.path.join(BASE_DIR, ".env"))

# -------------------------------------------------
# APP ENVIRONMENT
# local       -> SQL Server / SSMS
# production  -> Hostinger MySQL
# -------------------------------------------------
APP_ENV = os.getenv("APP_ENV", "local").lower().strip()

# -------------------------------------------------
# LOCAL SQL SERVER SETTINGS
# Used only when APP_ENV=local
# -------------------------------------------------
LOCAL_SQL_DRIVER = os.getenv("LOCAL_SQL_DRIVER", "ODBC Driver 17 for SQL Server")
LOCAL_SQL_SERVER = os.getenv("LOCAL_SQL_SERVER", "DESKTOP-QBPLIVH")
LOCAL_SQL_DB = os.getenv("LOCAL_SQL_DB", "PyMatch")
LOCAL_SQL_TRUSTED = os.getenv("LOCAL_SQL_TRUSTED", "yes").lower().strip()
LOCAL_SQL_USER = os.getenv("LOCAL_SQL_USER", "")
LOCAL_SQL_PASSWORD = os.getenv("LOCAL_SQL_PASSWORD", "")
LOCAL_SQL_PORT = os.getenv("LOCAL_SQL_PORT", "")
LOCAL_SQL_ENCRYPT = os.getenv("LOCAL_SQL_ENCRYPT", "no").lower().strip()
LOCAL_SQL_TRUST_CERT = os.getenv("LOCAL_SQL_TRUST_CERT", "yes").lower().strip()

# -------------------------------------------------
# PRODUCTION HOSTINGER MYSQL SETTINGS
# Used only when APP_ENV=production
# -------------------------------------------------
PROD_MYSQL_HOST = os.getenv("PROD_MYSQL_HOST", "auth-db1644.hstgr.io")
PROD_MYSQL_PORT = int(os.getenv("PROD_MYSQL_PORT", "3306"))
PROD_MYSQL_DB = os.getenv("PROD_MYSQL_DB", "u943862301_PyMatch")
PROD_MYSQL_USER = os.getenv("PROD_MYSQL_USER", "u943862301_PyMatch")
PROD_MYSQL_PASSWORD = os.getenv("PROD_MYSQL_PASSWORD", "")

# -------------------------------------------------
# ACTIVE DATABASE SETTINGS
# -------------------------------------------------
if APP_ENV == "production":
    DB_TYPE = "mysql"

    SQL_DRIVER = None
    SQL_SERVER = PROD_MYSQL_HOST
    SQL_DB = PROD_MYSQL_DB
    SQL_TRUSTED = "no"
    SQL_USER = PROD_MYSQL_USER
    SQL_PASSWORD = PROD_MYSQL_PASSWORD
    SQL_PORT = str(PROD_MYSQL_PORT)
    SQL_ENCRYPT = "no"
    SQL_TRUSTCERT = "no"
else:
    DB_TYPE = "sqlserver"

    SQL_DRIVER = LOCAL_SQL_DRIVER
    SQL_SERVER = LOCAL_SQL_SERVER
    SQL_DB = LOCAL_SQL_DB
    SQL_TRUSTED = LOCAL_SQL_TRUSTED
    SQL_USER = LOCAL_SQL_USER
    SQL_PASSWORD = LOCAL_SQL_PASSWORD
    SQL_PORT = LOCAL_SQL_PORT
    SQL_ENCRYPT = LOCAL_SQL_ENCRYPT
    SQL_TRUSTCERT = LOCAL_SQL_TRUST_CERT

# -------------------------------------------------
# COMMON APP SETTINGS
# -------------------------------------------------
PROGRESS_TBL = os.getenv("PYMATCH_PROGRESS_TABLE", "LLMGeneratedQuestions")
DEFAULT_N_QUESTIONS = int(os.getenv("PYMATCH_DEFAULT_N_QUESTIONS", "20"))
DEFAULT_BATCH_SIZE = int(os.getenv("PYMATCH_DEFAULT_BATCH_SIZE", "10"))
MAX_QUESTIONS = int(os.getenv("PYMATCH_MAX_QUESTIONS", "50"))

# -------------------------------------------------
# CONSTANTS USED ACROSS THE APP
# -------------------------------------------------
COLOR_KEYS = ["blue", "green", "red", "yellow"]
DOMAINS = ["marriage", "interview", "partnership", "general"]

# Optional debug
print(f"[config] APP_ENV = {APP_ENV}")
print(f"[config] DB_TYPE = {DB_TYPE}")

if APP_ENV == "local":
    print(f"[config] Using LOCAL SQL Server DB: {LOCAL_SQL_DB} on {LOCAL_SQL_SERVER}")
else:
    print(f"[config] Using PROD MySQL DB: {PROD_MYSQL_DB} on {PROD_MYSQL_HOST}:{PROD_MYSQL_PORT}")