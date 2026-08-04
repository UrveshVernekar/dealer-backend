from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from urllib.parse import unquote


def _parse_db_url(db_url: str):
    if not db_url.startswith("postgresql"):
        raise ValueError("Unsupported database URL scheme")

    scheme, rest = db_url.split("://", 1)
    if not rest:
        raise ValueError("Database URL is empty")

    if "@" not in rest:
        raise ValueError("Database URL must include credentials and host")

    creds, host_part = rest.rsplit("@", 1)
    if ":" not in creds:
        raise ValueError("Database URL must include a username and password")

    user, password = creds.split(":", 1)
    user = unquote(user)
    password = unquote(password)

    if "/" not in host_part:
        raise ValueError("Database URL must include a database name")

    host_port, database = host_part.split("/", 1)
    database = database.split("?", 1)[0].strip()

    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host = host_port
        port = 5432

    return host, port, user, password, database


# Function to auto-create target database in PostgreSQL if it doesn't exist
def create_database_if_not_exists():
    db_url = settings.DATABASE_URL
    if not db_url.startswith("postgresql"):
        return

    try:
        host, port, user, password, target_db = _parse_db_url(db_url)

        conn = psycopg2.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (target_db,)
        )
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(f"CREATE DATABASE {target_db}")
            print(f"PostgreSQL database '{target_db}' created successfully.")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Failed to check/create PostgreSQL database: {e}")


# Run the database creation check
try:
    create_database_if_not_exists()
except Exception as e:
    print(f"Database initialization warning: {e}")

try:
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"Database engine initialization warning: {e}")
    engine = None
    SessionLocal = None
    Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

