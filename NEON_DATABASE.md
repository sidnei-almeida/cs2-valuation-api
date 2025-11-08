# 🗄️ Neon.tech Database Configuration Guide

![Neon](https://img.shields.io/badge/Neon.Tech-PostgreSQL-00E599.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Status](https://img.shields.io/badge/Status-Configured-success.svg?style=for-the-badge)

> **Complete guide** for setting up and configuring PostgreSQL database on Neon.tech for the CS2 Valuation API.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Connection String](#-connection-string)
- [Local Development Setup](#-local-development-setup)
- [Render Deployment Configuration](#-render-deployment-configuration)
- [Database Initialization](#-database-initialization)
- [Testing Connection](#-testing-connection)
- [SSL Configuration](#-ssl-configuration)
- [Troubleshooting](#-troubleshooting)
- [Best Practices](#-best-practices)

---

## 🎯 Overview

This project uses **Neon.tech** for PostgreSQL hosting, providing:

| Feature | Benefit |
|---------|---------|
| 🚀 **Serverless** | Automatic scaling, no server management |
| 🔒 **SSL/TLS** | Encrypted connections required |
| 💰 **Free Tier** | Generous free tier for development |
| 🔄 **Connection Pooling** | Built-in pooling for better performance |
| 📊 **Monitoring** | Built-in metrics and monitoring |

---

## 🔗 Connection String

### Current Configuration

```
postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

### Connection String Components

| Component | Value | Description |
|-----------|-------|-------------|
| **Protocol** | `postgresql://` | Connection protocol |
| **User** | `neondb_owner` | Database username |
| **Password** | `npg_IQagKh8yZE4A` | Database password |
| **Host** | `ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech` | Neon.tech endpoint (with pooling) |
| **Database** | `neondb` | Database name |
| **SSL Mode** | `require` | SSL connection required |
| **Channel Binding** | `require` | Additional security layer |

> **Note**: The `-pooler` suffix in the hostname enables connection pooling, which is recommended for serverless applications.

---

## 💻 Local Development Setup

### Step 1: Create `.env` File

Create a `.env` file in the project root:

```bash
# Copy from example
cp env.example .env
```

### Step 2: Configure Environment Variables

Edit `.env` with your Neon.tech credentials:

```bash
# Database Configuration
DATABASE_URL="postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# PostgreSQL CLI Tools
PGUSER=neondb_owner
PGPASSWORD=npg_IQagKh8yZE4A

# Optional
PYTHON_VERSION=3.11.0
```

### Step 3: Verify Configuration

The application will automatically load variables from `.env` using `python-dotenv`.

---

## ☁️ Render Deployment Configuration

### Environment Variables Setup

In Render Dashboard → Your Service → **"Environment"**:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require` |
| `PGUSER` | `neondb_owner` |
| `PGPASSWORD` | `npg_IQagKh8yZE4A` |

### Alternative: Separate Components

If you prefer separate components:

```bash
DB_HOST=ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech
DB_PORT=5432
DB_NAME=neondb
DB_USER=neondb_owner
DB_PASSWORD=npg_IQagKh8yZE4A
```

> **Note**: The application will automatically add SSL parameters when using separate components.

---

## 🗄️ Database Initialization

### Method 1: Via API Endpoint

After deployment, initialize tables:

```bash
curl "https://your-service.onrender.com/api/db/init?admin_key=YOUR_ADMIN_KEY"
```

**Response**:
```json
{
  "success": true,
  "duration": 1.23,
  "tables_created": 2,
  "indices_created": 1,
  "metadata_records": 2
}
```

### Method 2: Via Migration Script

Run locally pointing to Neon.tech:

```bash
export DATABASE_URL="postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
python migrate_db.py
```

### Method 3: Manual SQL

Connect via `psql` and run:

```sql
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
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skin_prices_market_hash_name
ON skin_prices(market_hash_name);
```

---

## 🧪 Testing Connection

### Using psql

```bash
# Full connection string
psql 'postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

# Or using environment variables
export PGUSER=neondb_owner
export PGPASSWORD=npg_IQagKh8yZE4A
psql -h ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech -d neondb
```

### Using Python Script

Create `test_connection.py`:

```python
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    print("✅ Connection successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    print(f"PostgreSQL version: {cursor.fetchone()[0]}")
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

Run:
```bash
python test_connection.py
```

### Using API Test Script

The project includes `test_db_connection.py`:

```bash
python test_db_connection.py
```

---

## 🔒 SSL Configuration

### Why SSL is Required

Neon.tech requires SSL/TLS encryption for all connections. The connection string includes:

- `sslmode=require`: Enforces SSL connection
- `channel_binding=require`: Additional security layer

### SSL Modes

The application automatically tries these modes in order:

1. `require` - SSL required (used by Neon.tech)
2. `prefer` - SSL preferred, fallback to non-SSL
3. `verify-ca` - Verify certificate authority
4. `verify-full` - Full certificate verification

### Troubleshooting SSL

If you encounter SSL errors:

1. **Verify connection string** includes `sslmode=require`
2. **Check certificate** validity
3. **Test connection** using `psql` first
4. **Review logs** for specific SSL error messages

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Connection Timeout

**Symptoms**: Connection hangs or times out

**Solutions**:
- Verify hostname is correct
- Check network connectivity
- Ensure SSL parameters are included
- Try connection pooling endpoint (`-pooler`)

#### 2. Authentication Failed

**Symptoms**: `FATAL: password authentication failed`

**Solutions**:
- Verify username and password
- Check for special characters in password (may need URL encoding)
- Ensure user has proper permissions

#### 3. SSL Required Error

**Symptoms**: `SSL connection is required`

**Solutions**:
- Add `sslmode=require` to connection string
- Verify `channel_binding=require` is present
- Check Neon.tech SSL requirements

#### 4. Database Does Not Exist

**Symptoms**: `database "neondb" does not exist`

**Solutions**:
- Verify database name in connection string
- Create database in Neon.tech dashboard if needed
- Check database name spelling

### Getting Help

1. **Check Neon.tech Dashboard**: Monitor connection metrics
2. **Review Application Logs**: Check for specific error messages
3. **Test Connection Locally**: Isolate deployment vs. connection issues
4. **Neon.tech Support**: Contact support for database-specific issues

---

## 💡 Best Practices

### Connection Management

- ✅ **Use Connection Pooling**: Always use `-pooler` endpoint
- ✅ **Set Timeouts**: Configure appropriate connection timeouts
- ✅ **Monitor Connections**: Track active connections in Neon dashboard
- ✅ **Close Connections**: Always close connections after use

### Security

- ✅ **Never Commit Credentials**: Keep `.env` in `.gitignore`
- ✅ **Use SSL**: Always require SSL connections
- ✅ **Rotate Passwords**: Regularly update database passwords
- ✅ **Limit Access**: Restrict database access to necessary IPs

### Performance

- ✅ **Use Indexes**: Ensure proper indexes on frequently queried columns
- ✅ **Monitor Queries**: Track slow queries in Neon dashboard
- ✅ **Optimize Connections**: Use connection pooling for serverless
- ✅ **Cache When Possible**: Use application-level caching

### Backup & Recovery

- ✅ **Enable Point-in-Time Recovery**: Available in Neon.tech paid plans
- ✅ **Regular Backups**: Export data regularly for free tier
- ✅ **Test Restores**: Verify backup restoration process
- ✅ **Document Procedures**: Keep backup/restore procedures documented

---

## 📚 Additional Resources

- [Neon.tech Documentation](https://neon.tech/docs)
- [PostgreSQL SSL Configuration](https://www.postgresql.org/docs/current/libpq-ssl.html)
- [Connection String Format](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
- [Project README](README.md)
- [Render Deployment Guide](RENDER_DEPLOY.md)

---

<div align="center">

**Database Ready?** [Deploy on Render](RENDER_DEPLOY.md) · [View API Docs](README.md#api-documentation)

</div>
