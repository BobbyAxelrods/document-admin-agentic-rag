import os
import sys

print("Starting debug script...")

try:
    import pg8000
    print("pg8000 imported successfully.")
except ImportError:
    print("ERROR: pg8000 not found.")

try:
    from google.cloud.sql.connector import Connector, IPTypes
    print("google.cloud.sql.connector imported successfully.")
except ImportError:
    print("ERROR: google.cloud.sql.connector not found.")

from dotenv import load_dotenv

# Load .env file explicitly
env_path = os.path.join(os.path.dirname(__file__), 'rag', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded .env from {env_path}")
else:
    print(f"WARNING: .env not found at {env_path}")

# Get config
INSTANCE_CONNECTION_NAME = "prudential-poc-484904:asia-east1:file-metadata"
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_NAME = os.getenv("DB_NAME", "rag_metadata")

# Mask password for display
masked_pass = "*" * len(DB_PASS) if DB_PASS else "None"

print("Database Configuration:")
print(f"  Instance: {INSTANCE_CONNECTION_NAME}")
print(f"  User: {DB_USER}")
print(f"  Pass: {masked_pass}")
print(f"  Name: {DB_NAME}")

def test_connection():
    try:
        print("Attempting to connect to database using Cloud SQL Python Connector...")
        
        connector = Connector()
        
        def getconn() -> pg8000.dbapi.Connection:
            conn: pg8000.dbapi.Connection = connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                ip_type=IPTypes.PUBLIC,
            )
            return conn
            
        conn = getconn()
        print("SUCCESS: Connected to database!")
        
        # Check if tables exist
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = cur.fetchall()
            print(f"Existing tables: {[t[0] for t in tables]}")
        finally:
            cur.close()
            
        conn.close()
        # Cleanup connector
        connector.close()
        
    except Exception as e:
        print(f"FAILURE: Could not connect to database.")
        print(f"Error details: {e}")

if __name__ == "__main__":
    test_connection()
