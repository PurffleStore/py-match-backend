# config.py
import os
from dotenv import load_dotenv

# --- load .env so OPENAI_API_KEY (and others) are available ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables - priority: Hugging Face secrets > .env file
IS_HUGGING_FACE = os.environ.get('HUGGINGFACE_SPACES') == 'true' or os.environ.get('SPACE_ID') is not None
if not IS_HUGGING_FACE:
    # Only load from .env file when running locally
    load_dotenv(os.path.join(BASE_DIR, ".env"))
else:
    # On Hugging Face, secrets are automatically available as environment variables
    print("Running on Hugging Face Spaces - using secrets from environment variables")

if IS_HUGGING_FACE:
    # Hugging Face Spaces configuration
    DEFAULT_SQL_SERVER = "pykara-sqlserver.c5aosm6ie5j3.eu-north-1.rds.amazonaws.com,1433"
    DEFAULT_SQL_DB = "PyMatch"
    DEFAULT_SQL_TRUSTED = "yes"  # Use SQL authentication on Hugging Face
else:
    # Local development configuration
    DEFAULT_SQL_SERVER = "DESKTOP-QBPLIVH"
    DEFAULT_SQL_DB = "PyMatch"
    DEFAULT_SQL_TRUSTED = "yes"  # Use Windows authentication locally

SQL_DRIVER   = os.getenv("PYMATCH_SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_SERVER   = os.getenv("PYMATCH_SQL_SERVER", DEFAULT_SQL_SERVER)
SQL_DB       = os.getenv("PYMATCH_SQL_DB", DEFAULT_SQL_DB)
SQL_TRUSTED  = os.getenv("PYMATCH_SQL_TRUSTED", DEFAULT_SQL_TRUSTED)  # yes/no
SQL_USER      = os.getenv("PYMATCH_SQL_USER", "")
SQL_PASSWORD  = os.getenv("PYMATCH_SQL_PASSWORD", "")
SQL_PORT      = os.getenv("PYMATCH_SQL_PORT", "")
SQL_ENCRYPT   = os.getenv("PYMATCH_SQL_ENCRYPT", "no").lower().strip()
SQL_TRUSTCERT = os.getenv("PYMATCH_SQL_TRUST_CERT", "yes").lower().strip()

PROGRESS_TBL = os.getenv("PYMATCH_PROGRESS_TABLE", "LLMGeneratedQuestions")
DEFAULT_N_QUESTIONS = int(os.getenv("PYMATCH_DEFAULT_N_QUESTIONS", "20"))
DEFAULT_BATCH_SIZE = int(os.getenv("PYMATCH_DEFAULT_BATCH_SIZE", "10"))
MAX_QUESTIONS = int(os.getenv("PYMATCH_MAX_QUESTIONS", "50"))

# Some constants used across the app
COLOR_KEYS = ["blue", "green", "red", "yellow"]
DOMAINS = ["marriage", "interview", "partnership", "general"]

# # Faiss index / chunks defaults - user should update FAISS_INDEX_PATH or provide companion chunks file
# FAISS_INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faiss_index_file.index")