import psycopg2
from app.config import Config
from psycopg2.extras import RealDictCursor

DB_PARAMS = Config.POSTGRESQL_PARAM

# Function to connect to PostgreSQL
def connect_db():
    try:
        conn = psycopg2.connect(**DB_PARAMS, cursor_factory=RealDictCursor)
        # print("Connected to the database")
        return conn
    except Exception as e:
        print(f"Error: {e}")
        return None