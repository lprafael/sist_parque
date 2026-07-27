import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

print("=== Settings DATABASE_URL (used by FastAPI & AsyncSessionLocal) ===")
print("  DATABASE_URL:", settings.DATABASE_URL)
print("  DB_HOST:", settings.DB_HOST)
print("  DB_PORT:", settings.DB_PORT)
print("  DB_NAME:", settings.DB_NAME)
print("  DB_USER:", settings.DB_USER)
print("  DB_PASSWORD:", settings.DB_PASSWORD)
print("  DB_SCHEMA:", settings.DB_SCHEMA)

from migrations.migrate_excel import DB_CONFIG
print("\n=== DB_CONFIG (used by migrate_excel.py) ===")
print("  DB_CONFIG:", DB_CONFIG)
