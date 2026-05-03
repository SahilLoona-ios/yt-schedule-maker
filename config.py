# ============================================================
#  config.py — Single source of truth. Edit ONLY this file.
# ============================================================

# --- Watch Schedule ---
WEEKDAY_BUDGET_HOURS: float = 1.5    # Mon–Fri
WEEKEND_BUDGET_HOURS: float = 3.0    # Sat & Sun
REVISION_MINUTES: int       = 30     # Added after EACH video for revision/practice

# --- Video Fetch Range ---
VIDEOS_START_DATE: str = "2026-01-01"   # Fetch videos uploaded from this date

# --- Output ---
OUTPUT_FILE: str = "yt_schedule.xlsx"
STATE_FILE: str  = "state.json"         # Tracks last run to avoid duplicates

# --- Google OAuth ---
CLIENT_SECRET_FILE: str = "client_secret.json"
TOKEN_FILE: str         = "token.pickle"
SCOPES: list            = ["https://www.googleapis.com/auth/youtube.readonly"]

# --- API ---
API_BATCH_SIZE: int    = 50
MAX_SUBSCRIPTIONS: int = 1000

# --- Channel Filter ---
# These channels are always skipped regardless of topic
SKIP_CHANNELS: list = [
    "iOS Labs",
    "tunsdev",
    "Paul Hudson",
]

# Wikipedia topic keywords that indicate a FINANCE channel → exclude
FINANCE_TOPIC_KEYWORDS: list = [
    "Finance", "Economy", "Business", "Investment",
    "Accounting", "Insurance", "Market"
]

# Wikipedia topic keywords that indicate a TECH channel → include
TECH_TOPIC_KEYWORDS: list = [
    "Technology", "Computing", "Software", "Engineering",
    "Internet", "Electronics", "Science"
]

# Fallback: keywords checked in channel name + description
FINANCE_DESC_KEYWORDS: list = [
    "finance", "investing", "investment", "stock market", "trading",
    "economy", "banking", "wealth management", "tax", "accounting",
    "mutual fund", "portfolio", "nse", "bse", "sensex", "nifty",
    "cryptocurrency", "crypto", "forex", "financial planning",
    "share market", "equity", "demat", "sip ", "smallcase"
]

TECH_DESC_KEYWORDS: list = [
    "programming", "coding", "software", "developer", "tech",
    "computer science", "python", "javascript", "java", "flutter",
    "web dev", "data science", "machine learning", "ai", "devops",
    "cloud", "linux", "android", "react", "node", "database",
    "algorithm", "open source", "github", "docker", "kubernetes"
]
