# CS2 Valuation API

![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-05998B.svg?style=for-the-badge&logo=fastapi&logoColor=white)
![Render](https://img.shields.io/badge/Deployed%20on-Render-3A56D4.svg?style=for-the-badge&logo=render&logoColor=white)
![Neon](https://img.shields.io/badge/Database-Neon.Tech-00E599.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?style=for-the-badge&logo=postgresql&logoColor=white)

> **Professional-grade API** for evaluating Counter-Strike 2 inventories with intelligent price scraping, storage unit analysis, and Steam OpenID authentication.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [Deployment on Render](#-deployment-on-render)
- [Database Setup (Neon.tech)](#-database-setup-neontech)
- [API Documentation](#-api-documentation)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)

---

## 🎯 Overview

The **CS2 Valuation API** is a production-ready REST API designed to evaluate Counter-Strike 2 inventories with a focus on Storage Units and rare items. The platform provides:

- **Intelligent Price Scraping**: Robust collection layer with fallback mechanisms and anti-blocking heuristics
- **Real-time Inventory Analysis**: Complete evaluation by item, category, rarity, and float value
- **Storage Unit Support**: Authenticated access to user's Storage Unit contents
- **Steam Integration**: Secure login and item ownership verification via Steam OpenID
- **Production Ready**: Fully configured for deployment on Render with PostgreSQL (Neon.tech)

The API is currently used in production by a frontend hosted on GitHub Pages, but can be integrated into any application.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🎯 **Smart Scraping** | Multi-source price collection with automatic fallback and rate limiting |
| 📊 **Inventory Analysis** | Complete evaluation by category, rarity, float value, and market trends |
| 🗄️ **Storage Units** | Authenticated access to Storage Unit contents (user's own units only) |
| 🔐 **Steam OpenID** | Secure authentication and ownership verification |
| 💾 **Database Cache** | PostgreSQL caching with automatic weekly updates |
| 📈 **Health Monitoring** | Built-in health checks and status endpoints |
| 🚀 **Production Ready** | Docker, Procfile, and Render configuration included |

---

## 🏗️ Architecture

```
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────────────┐
│    Frontend     │────────▶│   CS2 Valuation API  │────────▶│   Neon.tech (PG)    │
│  (GitHub Pages) │         │  (FastAPI + Gunicorn)│         │   Cache & Reports   │
└─────────────────┘         └──────────────────────┘         └─────────────────────┘
         │                            │                                │
         │                            └────────────┬───────────────────┘
         │                                         │
         ▼                                         ▼
   Steam OpenID                          Scraping Services
  (Authentication)              (Steam Market, CSGOSkins, etc.)
```

### Component Overview

- **API Layer**: FastAPI with async/await support, automatic OpenAPI documentation
- **Database Layer**: PostgreSQL with connection pooling, SSL support, and fallback to in-memory cache
- **Scraping Layer**: Multi-source price collection with intelligent retry logic
- **Authentication**: Steam OpenID integration for secure user verification

---

## 🛠️ Tech Stack

| Category | Technology |
|----------|-----------|
| **Language** | Python 3.11 |
| **Web Framework** | FastAPI + Uvicorn/Gunicorn |
| **Database** | PostgreSQL (Neon.tech) |
| **ORM/Driver** | psycopg2 |
| **Authentication** | Steam OpenID |
| **Deployment** | Render.com |
| **Containerization** | Docker (optional) |
| **Environment** | python-dotenv |
| **HTTP Client** | requests |
| **HTML Parsing** | selectolax |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (Neon.tech recommended)
- Git

### Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/cotacao_cs2.git
cd cotacao_cs2

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp env.example .env
# Edit .env with your DATABASE_URL and other variables

# 5. Initialize database (first time only)
python migrate_db.py

# 6. Run the API
python main.py
```

The API will be available at `http://127.0.0.1:8000` with interactive documentation at `/docs`.

---

## 🔐 Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Complete PostgreSQL connection string | `postgresql://user:pass@host/db?sslmode=require` |
| `PGUSER` | Database user for CLI tools | `neondb_owner` |
| `PGPASSWORD` | Database password | `your_password` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | Auto-generated |
| `STEAM_API_KEY` | Steam API key for advanced features | None |
| `PYTHON_VERSION` | Python version for Render | `3.11.0` |
| `PORT` | Server port | `8000` (local) / `$PORT` (Render) |

> **Note**: For local development, create a `.env` file in the project root. For production (Render), configure these in the dashboard's Environment Variables section.

---

## ☁️ Deployment on Render

This project is fully configured for deployment on [Render.com](https://render.com/).

### Quick Deploy Steps

1. **Create a Web Service** on Render
   - Connect your GitHub repository
   - Set **Root Directory** to `cotacao_cs2`
   - Select **Python 3** environment

2. **Configure Build & Start Commands**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 120 --keep-alive 120 main:app -b 0.0.0.0:$PORT
   ```

3. **Set Environment Variables**
   - `DATABASE_URL`: Your Neon.tech connection string
   - `PGUSER`: Database user
   - `PGPASSWORD`: Database password
   - `PYTHON_VERSION`: `3.11.0`

4. **Initialize Database**
   - After first deployment, visit: `https://your-service.onrender.com/api/db/init`
   - Or run locally: `python migrate_db.py`

### Alternative: Deploy via Blueprint

The project includes `render.yaml` for automated deployment:

1. In Render Dashboard, click **"New +"** → **"Blueprint"**
2. Connect your repository
3. Render will automatically detect and configure the service

📖 **Detailed Guide**: See [RENDER_DEPLOY.md](RENDER_DEPLOY.md) for complete instructions.

---

## 🗄️ Database Setup (Neon.tech)

This project uses **Neon.tech** for PostgreSQL hosting, providing:

- ✅ Serverless PostgreSQL with automatic scaling
- ✅ Connection pooling built-in
- ✅ SSL/TLS encryption required
- ✅ Free tier available

### Connection String

```
postgresql://neondb_owner:npg_IQagKh8yZE4A@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

### Database Initialization

After setting up your connection string:

```bash
# Option 1: Via API endpoint
curl "https://your-service.onrender.com/api/db/init?admin_key=YOUR_KEY"

# Option 2: Via migration script
export DATABASE_URL="your-connection-string"
python migrate_db.py
```

📖 **Complete Guide**: See [NEON_DATABASE.md](NEON_DATABASE.md) for detailed setup, troubleshooting, and best practices.

---

## 📚 API Documentation

### Interactive Documentation

Once the API is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | API status and component health |
| `/healthcheck` | GET | Simple health check for Render |
| `/api/inventory/{steamid}` | GET | Get inventory value for a Steam ID |
| `/api/db/init` | GET | Initialize database tables |
| `/api/db/stats` | GET | Database statistics (requires auth) |

### Authentication

Some endpoints require Steam OpenID authentication. See the `/docs` endpoint for complete authentication flow.

---

## 📁 Project Structure

```
cotacao_cs2/
├── main.py                 # FastAPI application entry point
├── migrate_db.py          # Database initialization script
├── requirements.txt        # Python dependencies
├── render.yaml            # Render deployment configuration
├── Procfile               # Process configuration for Render
├── Dockerfile             # Docker configuration (optional)
├── .env                   # Environment variables (local)
├── env.example            # Environment variables template
│
├── auth/                  # Authentication module
│   └── steam_auth.py      # Steam OpenID integration
│
├── services/              # Business logic services
│   ├── steam_market.py    # Price scraping services
│   ├── steam_inventory.py # Inventory analysis
│   └── case_evaluator.py  # Case opening evaluation
│
└── utils/                 # Utility modules
    ├── database.py        # Database connection and operations
    ├── config.py          # Configuration management
    ├── price_updater.py   # Scheduled price updates
    └── scraper.py         # Web scraping utilities
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add docstrings to all functions
- Include type hints where possible
- Update documentation for new features
- Test your changes locally before submitting

---

## 📄 License

This project is licensed under the MIT License. See the repository for details.

---

## 🔗 Additional Resources

- [Render Deployment Guide](RENDER_DEPLOY.md) - Complete deployment instructions
- [Neon.tech Database Guide](NEON_DATABASE.md) - Database setup and configuration
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Framework documentation
- [Neon.tech Documentation](https://neon.tech/docs) - Database provider docs

---

<div align="center">

**Built with ❤️ for the CS2 community**

[Report Bug](https://github.com/<your-username>/cotacao_cs2/issues) · [Request Feature](https://github.com/<your-username>/cotacao_cs2/issues) · [Documentation](https://github.com/<your-username>/cotacao_cs2#readme)

</div>
