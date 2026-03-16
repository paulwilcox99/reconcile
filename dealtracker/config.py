from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "dealtracker.db"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")

RECONCILIATION_TOLERANCE_USD = float(os.getenv("RECONCILE_TOLERANCE", "0.50"))
FUZZY_MATCH_THRESHOLD = float(os.getenv("FUZZY_THRESHOLD", "0.85"))

# Ensure required directories exist
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
