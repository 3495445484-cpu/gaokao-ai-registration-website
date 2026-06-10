import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.database import DB_PATH, initialize_database


if __name__ == "__main__":
    initialize_database()
    print(f"SQLite database initialized: {DB_PATH}")
