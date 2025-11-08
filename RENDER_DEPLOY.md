# 🚀 Deploy Guide: CS2 Valuation API on Render.com

![Render](https://img.shields.io/badge/Render-Deployment-3A56D4.svg?style=for-the-badge&logo=render&logoColor=white)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg?style=for-the-badge)

> **Complete step-by-step guide** for deploying the CS2 Valuation API on Render.com with PostgreSQL (Neon.tech).

---

## 📋 Table of Contents

- [Prerequisites](#-prerequisites)
- [Deployment Methods](#-deployment-methods)
- [Method 1: Dashboard Deployment](#-method-1-dashboard-deployment)
- [Method 2: Blueprint Deployment](#-method-2-blueprint-deployment)
- [Environment Variables Configuration](#-environment-variables-configuration)
- [Database Initialization](#-database-initialization)
- [Post-Deployment Checklist](#-post-deployment-checklist)
- [Troubleshooting](#-troubleshooting)
- [Best Practices](#-best-practices)

---

## ✅ Prerequisites

Before starting, ensure you have:

- ✅ [Render.com](https://render.com/) account (free tier available)
- ✅ GitHub repository with the API code
- ✅ Neon.tech PostgreSQL database (or Render PostgreSQL)
- ✅ Database connection credentials ready

---

## 🎯 Deployment Methods

This project supports two deployment methods:

| Method | Best For | Complexity |
|--------|----------|-----------|
| **Dashboard** | Manual control, custom settings | ⭐⭐ Medium |
| **Blueprint** | Quick setup, automated config | ⭐ Easy |

---

## 📝 Method 1: Dashboard Deployment

### Step 1: Create Web Service

1. Log in to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select the repository containing the API code

### Step 2: Configure Service Settings

| Setting | Value |
|---------|-------|
| **Name** | `cs2-valuation-api` (or your preferred name) |
| **Region** | Choose closest to your users |
| **Branch** | `main` (or your default branch) |
| **Root Directory** | `cotacao_cs2` ⚠️ **Important** |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 120 --keep-alive 120 main:app -b 0.0.0.0:$PORT` |
| **Python Version** | `3.11.0` |

### Step 3: Configure Environment Variables

Navigate to **"Environment"** tab and add:

#### Required Variables

```bash
DATABASE_URL=postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
PGUSER=neondb_owner
PGPASSWORD=npg_IQagKh8yZE4A
PYTHON_VERSION=3.11.0
```

#### Optional Variables

```bash
JWT_SECRET_KEY=your-secret-key-here  # Recommended for production
STEAM_API_KEY=your-steam-api-key     # For advanced features
```

### Step 4: Advanced Settings

In **"Advanced"** section:

- ✅ Enable **"Auto-Deploy"** (deploys on every push to main branch)
- ✅ Set **Health Check Path** to `/healthcheck`
- ✅ Configure **Health Check Timeout** to `300` seconds

### Step 5: Create Service

Click **"Create Web Service"** and wait for the initial deployment (2-5 minutes).

---

## 🎨 Method 2: Blueprint Deployment

### Step 1: Prepare Repository

Ensure `render.yaml` is in your repository root:

```yaml
services:
  - type: web
    name: cs2-valuation-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 120 --keep-alive 120 main:app -b 0.0.0.0:$PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
```

### Step 2: Deploy via Blueprint

1. In Render Dashboard, click **"New +"** → **"Blueprint"**
2. Connect your GitHub repository
3. Render will automatically detect `render.yaml`
4. Review the configuration and click **"Apply"**

### Step 3: Configure Environment Variables

After Blueprint creates the service:

1. Go to your service → **"Environment"** tab
2. Add all required environment variables (see Method 1, Step 3)

---

## 🔐 Environment Variables Configuration

### Database Options

#### Option 1: Neon.tech (Recommended) ⭐

```bash
DATABASE_URL=postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
PGUSER=neondb_owner
PGPASSWORD=npg_IQagKh8yZE4A
```

📖 See [NEON_DATABASE.md](NEON_DATABASE.md) for detailed setup.

#### Option 2: Render PostgreSQL

1. Create PostgreSQL service in Render
2. Link it to your web service: **"Environment"** → **"Link Resource"**
3. Render automatically creates `DATABASE_URL`

#### Option 3: External PostgreSQL

```bash
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=prefer
```

Or use separate components:

```bash
DB_HOST=your-host
DB_PORT=5432
DB_NAME=your-database
DB_USER=your-user
DB_PASSWORD=your-password
```

---

## 🗄️ Database Initialization

After successful deployment, initialize the database:

### Method 1: Via API Endpoint

```bash
curl "https://your-service.onrender.com/api/db/init?admin_key=YOUR_ADMIN_KEY"
```

> **Note**: Configure `ADMIN_KEY` environment variable if you want to protect this endpoint.

### Method 2: Via Migration Script (Local)

```bash
export DATABASE_URL="your-connection-string"
python migrate_db.py
```

### Verify Database

Check if tables were created:

```bash
curl "https://your-service.onrender.com/api/db/stats"
```

---

## ✅ Post-Deployment Checklist

- [ ] Service is running and healthy
- [ ] Database initialized successfully
- [ ] Health check endpoint responds: `/healthcheck`
- [ ] Status endpoint works: `/api/status`
- [ ] CORS configured for your frontend domain
- [ ] Environment variables are set correctly
- [ ] Auto-deploy is enabled (if desired)

### Update Frontend Configuration

Update your frontend to use the new API URL:

```javascript
const API_BASE_URL = isLocalhost 
  ? 'http://localhost:8000'  // Development
  : 'https://your-service.onrender.com';  // Production
```

### Update CORS Settings

Add your Render URL to `main.py`:

```python
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "https://your-frontend-domain.com",
    "https://your-service.onrender.com",  # Add this
]
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Build Fails

**Problem**: Build command fails during deployment

**Solutions**:
- Check `requirements.txt` for syntax errors
- Verify Python version compatibility
- Check build logs in Render dashboard

#### 2. Service Won't Start

**Problem**: Service crashes on startup

**Solutions**:
- Verify `DATABASE_URL` is correct
- Check start command syntax
- Review logs for specific error messages
- Ensure `$PORT` is used (not hardcoded port)

#### 3. Database Connection Errors

**Problem**: Cannot connect to database

**Solutions**:
- Verify `DATABASE_URL` format is correct
- Check SSL parameters (`sslmode=require`)
- Ensure database is accessible from Render's IPs
- Test connection string locally first

#### 4. Health Check Fails

**Problem**: Render reports service as unhealthy

**Solutions**:
- Verify `/healthcheck` endpoint exists
- Check endpoint returns 200 status
- Increase health check timeout if needed

### Getting Help

1. **Check Logs**: Render Dashboard → Your Service → **"Logs"**
2. **Test Locally**: Reproduce issue in local environment
3. **Review Documentation**: Check [NEON_DATABASE.md](NEON_DATABASE.md) for database-specific issues

---

## 💡 Best Practices

### Performance

- ✅ Use connection pooling (Neon.tech includes this)
- ✅ Enable auto-deploy only for production branch
- ✅ Monitor service metrics in Render dashboard
- ✅ Set appropriate timeouts for long-running requests

### Security

- ✅ Never commit `.env` files (already in `.gitignore`)
- ✅ Use strong `JWT_SECRET_KEY` in production
- ✅ Enable SSL for all database connections
- ✅ Restrict CORS to known domains only

### Monitoring

- ✅ Set up health check alerts
- ✅ Monitor database connection pool usage
- ✅ Track API response times
- ✅ Set up error notifications

### Cost Optimization

- ✅ Use free tier for development/testing
- ✅ Monitor resource usage
- ✅ Consider upgrading plan only when needed
- ✅ Use Neon.tech free tier for small projects

---

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [Neon.tech Setup Guide](NEON_DATABASE.md)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Project README](README.md)

---

<div align="center">

**Need Help?** [Open an Issue](https://github.com/<your-username>/cotacao_cs2/issues) · [View Logs](https://dashboard.render.com/)

</div>
