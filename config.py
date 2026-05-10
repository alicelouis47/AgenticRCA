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

TRINO_CONFIG_CSV = CONFIG_DIR / "trino_config.csv"
ATTR_LIST_CSV = CONFIG_DIR / "attribute_list.csv"
DB_SCHEMA_CSV = CONFIG_DIR / "drive_hd.csv"

# Ensure core directories exist
for d in [SKILLS_DIR, CONFIG_DIR, PROMPTS_DIR]:
    d.mkdir(exist_ok=True)
