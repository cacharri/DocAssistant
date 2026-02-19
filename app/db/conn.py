import psycopg
from app.core.config import settings

def get_conn():
    # psycopg v3 uses "postgresql://..." DSN
    # Our DATABASE_URL currently is "postgresql+psycopg://..."
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(dsn)
