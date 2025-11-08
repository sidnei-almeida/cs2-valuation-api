# CS2 Valuation API

API for evaluating Counter-Strike 2 inventories, especially for analyzing Storage Units and market items.

## Features

- Exclusive scraping for item prices
- Item classification by source (Storage Units or Market)
- Inventory analysis by categories
- Access to Storage Unit contents (only for authenticated user's own units)
- Authentication via Steam OpenID

## Local Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv .venv`
3. Activate the environment:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the API: `python main.py`

## Deploy on Render

### Option 1: Deploy via Dashboard

1. Create an account on [Render](https://render.com/)
2. In the Dashboard, click "New +" and select "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - Name: `cs2-valuation-api` (or another of your choice)
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -k uvicorn.workers.UvicornWorker -w 4 main:app -b 0.0.0.0:$PORT`
5. Click "Create Web Service"

### Option 2: Deploy via render.yaml

1. Make sure the `render.yaml` file is in the repository
2. In the Render Dashboard, click "New +" and select "Blueprint"
3. Connect your GitHub repository
4. Render will automatically detect the render.yaml file and create the configured services

## Frontend Connection on GitHub Pages

After deployment, your API will be available at a URL like:
`https://cs2-valuation-api.onrender.com`

The frontend on GitHub Pages should be configured to access this URL. CORS is already configured to allow requests from:
- `http://localhost:5500` (local development)
- `https://elite-skins-2025.github.io` (GitHub Pages)

## Environment Variables

If needed, you can configure the following environment variables:

- `DATABASE_URL`: PostgreSQL connection string (required for production)
  - Example (Neon.tech): `postgresql://user:password@host/dbname?sslmode=require&channel_binding=require`
- `SECRET_KEY`: Secret key for JWT (automatically generated if not provided)
- `STEAM_API_KEY`: Steam API key (optional, for advanced features)

### Database Configuration

This project uses PostgreSQL hosted on **Neon.tech**. See [NEON_DATABASE.md](NEON_DATABASE.md) for detailed configuration instructions. 