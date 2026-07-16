from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from urllib.parse import urlparse

# Function to auto-create target database in PostgreSQL if it doesn't exist
def create_database_if_not_exists():
    db_url = settings.DATABASE_URL
    if not db_url.startswith("postgresql"):
        return
        
    try:
        # custom parsing to support passwords with '#' or '$'
        # e.g., postgresql+psycopg2://materialsuser:materials1234#$@localhost:5432/dealer_db
        without_dialect = db_url.split("//", 1)[1]
        creds, host_part = without_dialect.rsplit("@", 1)
        user, password = creds.split(":", 1)
        
        host_port, target_db = host_part.split("/", 1)
        # remove optional query parameters
        if "?" in target_db:
            target_db = target_db.split("?", 1)[0]
            
        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 5432
            
        # Connect to default postgres DB
        conn = psycopg2.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database already exists
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{target_db}'")
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(f"CREATE DATABASE {target_db}")
            print(f"PostgreSQL database '{target_db}' created successfully.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Failed to check/create PostgreSQL database: {e}")


# Run the database creation check
create_database_if_not_exists()

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

