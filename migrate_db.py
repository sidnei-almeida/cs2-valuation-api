"""
Script to initialize tables in PostgreSQL database.
Run this script once after deployment to prepare the database.
Works with any PostgreSQL service (Render, Railway, Supabase, etc).
"""
import os
import psycopg2
from datetime import datetime
import time

# Database connection URL (configured via environment variables)
DATABASE_URL = os.environ.get('DATABASE_URL')

def init_database():
    """Initializes the database by creating necessary tables."""
    print(f"Starting database configuration...")
    start_time = time.time()
    
    if not DATABASE_URL:
        error_msg = """
        DATABASE_URL not configured!
        Configure the DATABASE_URL environment variable with the PostgreSQL connection URL.
        Example: postgresql://user:password@host:port/database
        """
        print(error_msg)
        return {
            "success": False,
            "error": "DATABASE_URL not configured",
            "duration": time.time() - start_time
        }
    
    try:
        # Connect to PostgreSQL
        db_info = DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else "database"
        print(f"Connecting to PostgreSQL at {db_info}...")
        
        # Try connecting with different SSL modes
        ssl_modes = ['prefer', 'require', 'verify-ca', 'verify-full']
        conn = None
        
        for ssl_mode in ssl_modes:
            try:
                if 'sslmode=' not in DATABASE_URL:
                    separator = '&' if '?' in DATABASE_URL else '?'
                    db_url_with_ssl = f"{DATABASE_URL}{separator}sslmode={ssl_mode}"
                else:
                    db_url_with_ssl = DATABASE_URL
                conn = psycopg2.connect(db_url_with_ssl, connect_timeout=20)
                print(f"Connection established with sslmode={ssl_mode}")
                break
            except Exception as e:
                if ssl_mode == ssl_modes[-1]:  # Last attempt
                    raise e
                continue
        
        if not conn:
            raise Exception("Could not establish connection to database")
        
        cursor = conn.cursor()
        
        # Create table to store skin prices
        print("Creating skin_prices table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS skin_prices (
            id SERIAL PRIMARY KEY,
            market_hash_name TEXT NOT NULL,
            price REAL NOT NULL,
            currency INTEGER NOT NULL,
            app_id INTEGER NOT NULL,
            last_updated TIMESTAMP NOT NULL,
            last_scraped TIMESTAMP NOT NULL,
            update_count INTEGER DEFAULT 1,
            UNIQUE(market_hash_name, currency, app_id)
        )
        ''')
        
        # Create table to store metadata and configurations
        print("Creating metadata table...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        ''')
        
        # Create index for fast searches by market_hash_name
        print("Creating index for market_hash_name...")
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_skin_prices_market_hash_name
        ON skin_prices(market_hash_name)
        ''')
        
        # Insert configuration record
        print("Inserting initial configuration record...")
        now = datetime.now()
        cursor.execute('''
        INSERT INTO metadata (key, value, updated_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        ''', ('db_initialized', 'true', now))
        
        # Insert record with last update date
        cursor.execute('''
        INSERT INTO metadata (key, value, updated_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        ''', ('last_update', now.isoformat(), now))
        
        conn.commit()
        
        # Verify tables were created
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('skin_prices', 'metadata')")
        table_count = cursor.fetchone()[0]
        
        # Verify indexes were created
        cursor.execute("SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'idx_skin_prices_market_hash_name'")
        index_count = cursor.fetchone()[0]
        
        # Verify metadata records
        cursor.execute("SELECT COUNT(*) FROM metadata")
        metadata_count = cursor.fetchone()[0]
        
        conn.close()
        
        duration = time.time() - start_time
        
        print(f"Initialization completed in {duration:.2f} seconds:")
        print(f"- Tables created: {table_count}/2")
        print(f"- Indexes created: {index_count}/1")
        print(f"- Metadata records: {metadata_count}/2")
        
        return {
            "success": True,
            "duration": duration,
            "tables_created": table_count,
            "indices_created": index_count,
            "metadata_records": metadata_count
        }
    
    except Exception as e:
        print(f"Error during database initialization: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "duration": time.time() - start_time
        }

if __name__ == "__main__":
    result = init_database()
    
    if result["success"]:
        print("\nPostgreSQL database initialized successfully!")
        print("The API will now use this database to store skin prices.")
    else:
        print(f"\nDatabase initialization failed: {result.get('error')}")
        print("The API will operate in fallback mode (memory) until the database is configured correctly.")

