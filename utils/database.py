import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import urllib.parse
import socket
import json
import threading

# Database connection URL (configured via environment variables)
# Supports Neon.tech, Render, Railway, and other PostgreSQL providers
# Example for Neon.tech: postgresql://user:password@host/dbname?sslmode=require&channel_binding=require
DATABASE_URL = os.environ.get('DATABASE_URL')

# Separate components as fallback (configured via environment variables)
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')

# In-memory cache for fallback mode
in_memory_db = {
    'skin_prices': {},
    'metadata': {}
}
db_lock = threading.Lock()
DB_AVAILABLE = False  # Flag to indicate if database is available

def get_db_connection():
    """Creates a connection to the PostgreSQL database."""
    global DB_AVAILABLE
    
    # List of SSL modes to try, in order of preference
    ssl_modes = ['require', 'prefer', 'verify-ca', 'verify-full']
    last_error = None
    
    # 1. First attempt: Use DATABASE_URL if available
    if DATABASE_URL:
        # If DATABASE_URL already has sslmode and channel_binding (e.g., Neon.tech), use it directly
        if 'sslmode=' in DATABASE_URL and 'channel_binding=' in DATABASE_URL:
            try:
                print(f"Attempting to connect with DATABASE_URL (with SSL and channel binding)")
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=20)
                print(f"Successfully connected with DATABASE_URL")
                DB_AVAILABLE = True
                return conn
            except Exception as e:
                print(f"Error connecting with DATABASE_URL: {e}")
                last_error = e
        else:
            # Try different SSL modes if not already specified
            for ssl_mode in ssl_modes:
                try:
                    print(f"Attempting to connect with DATABASE_URL and sslmode={ssl_mode}")
                    # Add sslmode to URL if not present
                    if 'sslmode=' not in DATABASE_URL:
                        separator = '&' if '?' in DATABASE_URL else '?'
                        db_url_with_ssl = f"{DATABASE_URL}{separator}sslmode={ssl_mode}"
                    else:
                        db_url_with_ssl = DATABASE_URL
                    conn = psycopg2.connect(db_url_with_ssl, connect_timeout=20)
                    print(f"Successfully connected with DATABASE_URL")
                    DB_AVAILABLE = True
                    return conn
                except Exception as e:
                    print(f"Error connecting with DATABASE_URL and sslmode={ssl_mode}: {e}")
                    last_error = e
    
    # 2. Second attempt: use separate components
    for ssl_mode in ssl_modes:
        try:
            connect_params = {
                'host': DB_HOST,
                'port': DB_PORT,
                'dbname': DB_NAME,
                'user': DB_USER,
                'password': DB_PASSWORD,
                'sslmode': ssl_mode,
                'connect_timeout': 15,
                'application_name': 'elite-skins-api',
                'keepalives': 1,
                'keepalives_idle': 30
            }
            
            print(f"Attempting to connect to PostgreSQL with separate parameters and sslmode={ssl_mode}")
            conn = psycopg2.connect(**connect_params)
            print(f"Successfully connected with separate parameters and sslmode={ssl_mode}")
            DB_AVAILABLE = True
            return conn
        except Exception as e:
            print(f"Error connecting with separate parameters and sslmode={ssl_mode}: {str(e)}")
            last_error = e
    
    # If we got here, all attempts failed
    error_msg = f"""
    PostgreSQL database connection error:
    - Host: {DB_HOST}
    - Port: {DB_PORT}
    - Database: {DB_NAME}
    - User: {DB_USER}
    - Error: {str(last_error)}
    - Suggestions:
      1. Check if PostgreSQL service is active
      2. Confirm credentials are correct in environment variables
      3. Verify DATABASE_URL or DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD are configured
      4. On Render, ensure PostgreSQL service is linked to web service
      
    ENTERING FALLBACK MODE: Data will be stored in memory temporarily.
    """
    print(error_msg)
    DB_AVAILABLE = False
    # Don't raise error, allowing application to continue in fallback mode
    return None

def init_db():
    """Initializes the database with necessary tables."""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Table to store skin prices
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
            
            # Table to store metadata and configurations
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            ''')
            
            # Index for fast searches by market_hash_name
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_skin_prices_market_hash_name
            ON skin_prices(market_hash_name)
            ''')
            
            conn.commit()
            conn.close()
            
            print(f"PostgreSQL database initialized")
        else:
            print("Database not available. Operating in fallback mode (memory).")
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("Operating in fallback mode (memory).")

def get_skin_price(market_hash_name: str, currency: int, app_id: int) -> Optional[float]:
    """
    Searches for a skin price in the database.
    
    Args:
        market_hash_name: Formatted item name for the market
        currency: Currency code
        app_id: Steam application ID
        
    Returns:
        Skin price or None if not found or outdated
    """
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                # Fallback to memory cache
                return _get_price_from_memory(market_hash_name, currency, app_id)
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('''
            SELECT price, last_updated FROM skin_prices
            WHERE market_hash_name = %s AND currency = %s AND app_id = %s
            ''', (market_hash_name, currency, app_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                price, last_updated = result['price'], result['last_updated']
                # Check if price is up to date (< 7 days)
                if datetime.now() - last_updated < timedelta(days=7):
                    return price
            
            return None
        except Exception as e:
            print(f"Error getting price from database: {e}")
            # Fallback para cache em memória
            return _get_price_from_memory(market_hash_name, currency, app_id)
    else:
        # Use memory cache when database is not available
        return _get_price_from_memory(market_hash_name, currency, app_id)

def _get_price_from_memory(market_hash_name: str, currency: int, app_id: int) -> Optional[float]:
    """Gets price from memory cache"""
    key = f"{market_hash_name}:{currency}:{app_id}"
    with db_lock:
        if key in in_memory_db['skin_prices']:
            item = in_memory_db['skin_prices'][key]
            if datetime.now() - item['last_updated'] < timedelta(days=7):
                return item['price']
    return None

def save_skin_price(market_hash_name: str, price: float, currency: int, app_id: int):
    """
    Saves or updates a skin price in the database.
    
    Args:
        market_hash_name: Formatted item name for the market
        price: Current skin price
        currency: Currency code
        app_id: Steam application ID
    """
    now = datetime.now()
    
    # Always save to memory cache
    key = f"{market_hash_name}:{currency}:{app_id}"
    with db_lock:
        in_memory_db['skin_prices'][key] = {
            'market_hash_name': market_hash_name,
            'price': price,
            'currency': currency,
            'app_id': app_id,
            'last_updated': now,
            'last_scraped': now,
            'update_count': 1
        }
    
    # Se o banco estiver disponível, tenta salvar nele também
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Check if item already exists
            cursor.execute('''
            SELECT id, update_count FROM skin_prices
            WHERE market_hash_name = %s AND currency = %s AND app_id = %s
            ''', (market_hash_name, currency, app_id))
            
            result = cursor.fetchone()
            
            if result:
                # Update existing item
                cursor.execute('''
                UPDATE skin_prices
                SET price = %s, last_updated = %s, update_count = update_count + 1
                WHERE id = %s
                ''', (price, now, result['id']))
            else:
                # Insert new item
                cursor.execute('''
                INSERT INTO skin_prices 
                (market_hash_name, price, currency, app_id, last_updated, last_scraped, update_count)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ''', (market_hash_name, price, currency, app_id, now, now))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving price to database: {e}")
            # Already in memory cache, so just log the error

def get_outdated_skins(days: int = 7, limit: int = 100) -> List[Dict]:
    """
    Returns a list of skins with outdated prices.
    
    Args:
        days: Number of days to consider a price outdated
        limit: Limit of records to return
        
    Returns:
        List of dictionaries with outdated skin information
    """
    if DB_AVAILABLE:
        try:
            outdated_date = datetime.now() - timedelta(days=days)
            conn = get_db_connection()
            if not conn:
                return _get_outdated_from_memory(days, limit)
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('''
            SELECT market_hash_name, price, currency, app_id, last_updated
            FROM skin_prices
            WHERE last_updated < %s
            ORDER BY last_updated ASC
            LIMIT %s
            ''', (outdated_date, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            return list(results)
        except Exception as e:
            print(f"Error getting outdated skins from database: {e}")
            return _get_outdated_from_memory(days, limit)
    else:
        return _get_outdated_from_memory(days, limit)

def _get_outdated_from_memory(days: int = 7, limit: int = 100) -> List[Dict]:
    """Gets outdated skins from memory cache"""
    outdated_date = datetime.now() - timedelta(days=days)
    results = []
    
    with db_lock:
        for key, item in in_memory_db['skin_prices'].items():
            if item['last_updated'] < outdated_date:
                results.append(item)
                if len(results) >= limit:
                    break
    
    return results

def update_last_scrape_time(market_hash_name: str, currency: int, app_id: int):
    """
    Updates the timestamp of the last time scraping was done for a skin.
    
    Args:
        market_hash_name: Formatted item name for the market
        currency: Currency code
        app_id: Steam application ID
    """
    now = datetime.now()
    
    # Update in memory cache
    key = f"{market_hash_name}:{currency}:{app_id}"
    with db_lock:
        if key in in_memory_db['skin_prices']:
            in_memory_db['skin_prices'][key]['last_scraped'] = now
    
    # If database is available, try to update there too
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE skin_prices
            SET last_scraped = %s
            WHERE market_hash_name = %s AND currency = %s AND app_id = %s
            ''', (now, market_hash_name, currency, app_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating scrape time in database: {e}")

def set_metadata(key: str, value: str):
    """
    Sets a metadata value in the database.
    
    Args:
        key: Metadata key
        value: Value to be stored
    """
    now = datetime.now()
    
    # Save to memory cache
    with db_lock:
        in_memory_db['metadata'][key] = {
            'value': value,
            'updated_at': now
        }
    
    # Se o banco estiver disponível, tenta salvar nele também
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO metadata (key, value, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            ''', (key, value, now))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving metadata to database: {e}")

def get_metadata(key: str, default: str = None) -> str:
    """
    Gets a metadata value from the database.
    
    Args:
        key: Metadata key
        default: Default value if key doesn't exist
        
    Returns:
        Metadata value or default value
    """
    # Check memory cache first
    with db_lock:
        if key in in_memory_db['metadata']:
            return in_memory_db['metadata'][key]['value']
    
    # If not found in memory and database is available, try to search there
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return default
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('SELECT value FROM metadata WHERE key = %s', (key,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Update memory cache
                with db_lock:
                    in_memory_db['metadata'][key] = {
                        'value': result['value'],
                        'updated_at': datetime.now()
                    }
                return result['value']
        except Exception as e:
            print(f"Error getting metadata from database: {e}")
            
    return default

def get_stats() -> Dict:
    """
    Returns statistics about the database.
    
    Returns:
        Dictionary with statistics
    """
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return _get_stats_from_memory()
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Total skins
            cursor.execute('SELECT COUNT(*) as total FROM skin_prices')
            total = cursor.fetchone()['total']
            
            # Average price
            cursor.execute('SELECT AVG(price) as avg_price FROM skin_prices')
            avg_price = cursor.fetchone()['avg_price']
            
            # Recently updated skins (7 days)
            recent_date = datetime.now() - timedelta(days=7)
            cursor.execute('SELECT COUNT(*) as recent FROM skin_prices WHERE last_updated > %s', (recent_date,))
            recent = cursor.fetchone()['recent']
            
            # Last update
            cursor.execute('SELECT MAX(last_updated) as last_update FROM skin_prices')
            last_update = cursor.fetchone()['last_update']
            
            conn.close()
            
            return {
                'total_skins': total,
                'average_price': round(avg_price, 2) if avg_price else 0,
                'recently_updated': recent,
                'last_update': last_update.isoformat() if last_update else None,
                'database_type': 'PostgreSQL',
                'mode': 'DB'
            }
        except Exception as e:
            print(f"Error getting statistics from database: {e}")
            return _get_stats_from_memory()
    else:
        return _get_stats_from_memory()

def _get_stats_from_memory() -> Dict:
    """Returns statistics based on memory cache"""
    with db_lock:
        prices = list(item['price'] for item in in_memory_db['skin_prices'].values())
        total = len(in_memory_db['skin_prices'])
        avg_price = sum(prices) / total if total > 0 else 0
        
        # Recently updated skins (7 days)
        recent_date = datetime.now() - timedelta(days=7)
        recent = sum(1 for item in in_memory_db['skin_prices'].values() if item['last_updated'] > recent_date)
        
        # Last update
        last_update = max([item['last_updated'] for item in in_memory_db['skin_prices'].values()]) if total > 0 else None
        
        return {
            'total_skins': total,
            'average_price': round(avg_price, 2),
            'recently_updated': recent,
            'last_update': last_update.isoformat() if last_update else None,
            'database_type': 'Memory',
            'mode': 'FALLBACK'
        } 