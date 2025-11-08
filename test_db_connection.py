#!/usr/bin/env python3
"""
Script para testar a conexão com o banco de dados Neon.tech
"""
import os
import sys

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using environment variables directly.")

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 not installed. Install it with: pip install psycopg2-binary")
    sys.exit(1)

def test_connection():
    """Testa a conexão com o banco de dados"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("Error: DATABASE_URL not found in environment variables")
        print("Make sure .env file exists and contains DATABASE_URL")
        return False
    
    print("=" * 60)
    print("Testing Neon.tech Database Connection")
    print("=" * 60)
    print(f"\nDATABASE_URL: {database_url[:50]}...")
    print(f"Host: ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech")
    print(f"User: neondb_owner")
    print(f"Database: neondb")
    print(f"SSL Mode: require")
    print(f"Channel Binding: require")
    print("\n" + "-" * 60)
    
    try:
        print("Attempting to connect...")
        conn = psycopg2.connect(database_url, connect_timeout=10)
        print("✓ Connection successful!")
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✓ PostgreSQL version: {version[:50]}...")
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"✓ Found {len(tables)} table(s):")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("⚠ No tables found. Run migrate_db.py to initialize the database.")
        
        cursor.close()
        conn.close()
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return True
        
    except psycopg2.OperationalError as e:
        print(f"✗ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if the DATABASE_URL is correct")
        print("2. Verify network connectivity")
        print("3. Check if SSL parameters are correct")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

