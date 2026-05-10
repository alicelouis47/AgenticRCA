import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
SKILLS_DIR = BASE_DIR / "skills"
CONFIG_DIR = BASE_DIR / "config"
PROMPTS_DIR = BASE_DIR / "prompts"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Trino connection overrides (can also be set via trino_config.csv)
TRINO_HTTP_SCHEME = os.getenv("TRINO_HTTP_SCHEME", "http")   # "http" or "https"
TRINO_VERIFY = os.getenv("TRINO_VERIFY", "true")             # "true", "false", or path to CA cert

TRINO_CONFIG_CSV = CONFIG_DIR / "trino_config.csv"
ATTR_LIST_CSV = CONFIG_DIR / "attribute_list.csv"
DB_SCHEMA_CSV = CONFIG_DIR / "drive_hd.csv"

# Ensure core directories exist
for d in [SKILLS_DIR, CONFIG_DIR, PROMPTS_DIR]:
    d.mkdir(exist_ok=True)
