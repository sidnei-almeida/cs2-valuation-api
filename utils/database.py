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
                detailed_data JSONB,
                image_url TEXT,
                UNIQUE(market_hash_name, currency, app_id)
            )
            ''')
            
            # Add new columns if they don't exist (for existing tables)
            cursor.execute('''
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='skin_prices' AND column_name='detailed_data') THEN
                    ALTER TABLE skin_prices ADD COLUMN detailed_data JSONB;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='skin_prices' AND column_name='image_url') THEN
                    ALTER TABLE skin_prices ADD COLUMN image_url TEXT;
                END IF;
            END $$;
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
            
            # Table to store price history for each skin
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                market_hash_name TEXT NOT NULL,
                date DATE NOT NULL,
                price_usd REAL NOT NULL,
                price_cents INTEGER NOT NULL,
                volume INTEGER,
                listings INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(market_hash_name, date)
            )
            ''')
            
            # Indexes for price_history table
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_history_market_hash_name
            ON price_history(market_hash_name)
            ''')
            
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_history_date
            ON price_history(date)
            ''')
            
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_history_market_hash_name_date
            ON price_history(market_hash_name, date DESC)
            ''')
            
            conn.commit()
            conn.close()
            
            print(f"PostgreSQL database initialized")
        else:
            print("Database not available. Operating in fallback mode (memory).")
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("Operating in fallback mode (memory).")

def get_skin_price(market_hash_name: str, currency: int, app_id: int) -> Optional[Dict]:
    """
    Searches for a skin price in the database.
    
    Args:
        market_hash_name: Formatted item name for the market
        currency: Currency code
        app_id: Steam application ID
        
    Returns:
        Dictionary with price and detailed data, or None if not found or outdated
        Format: {'price': float, 'detailed_data': dict, 'image_url': str} or None
    """
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                # Fallback to memory cache
                return _get_price_from_memory(market_hash_name, currency, app_id)
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('''
            SELECT price, last_updated, detailed_data, image_url FROM skin_prices
            WHERE market_hash_name = %s AND currency = %s AND app_id = %s
            ''', (market_hash_name, currency, app_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                price = result['price']
                last_updated = result['last_updated']
                detailed_data = result.get('detailed_data')
                image_url = result.get('image_url')
                
                # Check if price is up to date (< 7 days)
                if datetime.now() - last_updated < timedelta(days=7):
                    return {
                        'price': price,
                        'detailed_data': detailed_data,
                        'image_url': image_url
                    }
            
            return None
        except Exception as e:
            print(f"Error getting price from database: {e}")
            # Fallback para cache em memória
            return _get_price_from_memory(market_hash_name, currency, app_id)
    else:
        # Use memory cache when database is not available
        return _get_price_from_memory(market_hash_name, currency, app_id)

def _get_price_from_memory(market_hash_name: str, currency: int, app_id: int) -> Optional[Dict]:
    """Gets price from memory cache"""
    key = f"{market_hash_name}:{currency}:{app_id}"
    with db_lock:
        if key in in_memory_db['skin_prices']:
            item = in_memory_db['skin_prices'][key]
            if datetime.now() - item['last_updated'] < timedelta(days=7):
                return {
                    'price': item['price'],
                    'detailed_data': item.get('detailed_data'),
                    'image_url': item.get('image_url')
                }
    return None

def save_skin_price(market_hash_name: str, price: float, currency: int, app_id: int, 
                    detailed_data: Optional[Dict] = None, image_url: Optional[str] = None):
    """
    Saves or updates a skin price in the database.
    
    Args:
        market_hash_name: Formatted item name for the market
        price: Current skin price
        currency: Currency code
        app_id: Steam application ID
        detailed_data: Optional dictionary with detailed price data (all wear conditions, StatTrak, etc.)
        image_url: Optional URL of the item image
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
            'update_count': 1,
            'detailed_data': detailed_data,
            'image_url': image_url
        }
    
    print(f"💾 Tentando salvar no banco: {market_hash_name} | DB_AVAILABLE={DB_AVAILABLE} | DATABASE_URL={'SIM' if DATABASE_URL else 'NÃO'}")
    
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
            
            # Prepare detailed_data as JSON string
            detailed_data_json = json.dumps(detailed_data) if detailed_data else None
            
            if result:
                # Update existing item
                cursor.execute('''
                UPDATE skin_prices
                SET price = %s, last_updated = %s, update_count = update_count + 1,
                    detailed_data = %s, image_url = %s
                WHERE id = %s
                ''', (price, now, detailed_data_json, image_url, result['id']))
            else:
                # Insert new item
                cursor.execute('''
                INSERT INTO skin_prices 
                (market_hash_name, price, currency, app_id, last_updated, last_scraped, update_count, detailed_data, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s)
                ''', (market_hash_name, price, currency, app_id, now, now, detailed_data_json, image_url))
            
            conn.commit()
            conn.close()
            print(f"✓ Dados salvos no banco: {market_hash_name} (preço: ${price:.2f})")
        except Exception as e:
            print(f"✗ ERRO ao salvar no banco de dados: {e}")
            import traceback
            traceback.print_exc()
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


def save_price_history(market_hash_name: str, price_history_data: Dict) -> bool:
    """
    Salva o histórico de preços de uma skin na tabela price_history.
    
    Args:
        market_hash_name: Nome base da skin (sem wear condition)
        price_history_data: Dicionário com estrutura do PriceHistory (entries, all_time_high, etc.)
        
    Returns:
        True se salvou com sucesso, False caso contrário
    """
    if not price_history_data or not price_history_data.get("entries"):
        print(f"⚠ Nenhum histórico para salvar para {market_hash_name}")
        return False
    
    if not DB_AVAILABLE:
        print(f"⚠ Banco não disponível, não salvando histórico para {market_hash_name}")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            print(f"⚠ Não foi possível conectar ao banco para salvar histórico de {market_hash_name}")
            return False
        
        cursor = conn.cursor()
        entries = price_history_data.get("entries", [])
        saved_count = 0
        skipped_count = 0
        
        print(f"💾 Salvando {len(entries)} entradas de histórico para {market_hash_name}")
        
        for entry in entries:
            try:
                date_str = entry.get("date")
                price_usd = entry.get("price_usd")
                price_cents = entry.get("price_cents")
                volume = entry.get("volume")
                listings = entry.get("listings")
                
                if not date_str or price_usd is None:
                    skipped_count += 1
                    continue
                
                # Usar ON CONFLICT para evitar duplicatas (market_hash_name + date é UNIQUE)
                cursor.execute('''
                INSERT INTO price_history 
                (market_hash_name, date, price_usd, price_cents, volume, listings)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (market_hash_name, date) 
                DO UPDATE SET
                    price_usd = EXCLUDED.price_usd,
                    price_cents = EXCLUDED.price_cents,
                    volume = EXCLUDED.volume,
                    listings = EXCLUDED.listings
                ''', (market_hash_name, date_str, price_usd, price_cents, volume, listings))
                
                saved_count += 1
            except Exception as e:
                print(f"⚠ Erro ao salvar entrada de histórico {entry.get('date')}: {e}")
                skipped_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        print(f"✓ Histórico salvo: {saved_count} entradas para {market_hash_name} (puladas: {skipped_count})")
        return True
        
    except Exception as e:
        print(f"✗ ERRO ao salvar histórico de preços para {market_hash_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_price_history(market_hash_name: str, limit: int = 1000, start_date: str = None, end_date: str = None) -> List[Dict]:
    """
    Busca o histórico de preços de uma skin.
    
    Args:
        market_hash_name: Nome base da skin
        limit: Número máximo de registros a retornar
        start_date: Data inicial (formato YYYY-MM-DD)
        end_date: Data final (formato YYYY-MM-DD)
        
    Returns:
        Lista de dicionários com o histórico de preços
    """
    if not DB_AVAILABLE:
        return []
    
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = '''
        SELECT date, price_usd, price_cents, volume, listings
        FROM price_history
        WHERE market_hash_name = %s
        '''
        params = [market_hash_name]
        
        if start_date:
            query += ' AND date >= %s'
            params.append(start_date)
        
        if end_date:
            query += ' AND date <= %s'
            params.append(end_date)
        
        query += ' ORDER BY date DESC LIMIT %s'
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
        
    except Exception as e:
        print(f"Erro ao buscar histórico de preços: {e}")
        return [] 