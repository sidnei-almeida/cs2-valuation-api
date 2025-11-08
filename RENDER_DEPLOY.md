# Deploying the API on Render.com

This guide contains instructions for deploying the CS2 valuation API on Render.com.

## Prerequisites

- Account on [Render](https://render.com/)
- Git repository with the API code

## Step by step

### 1. Login to Render

Access the Render dashboard at [https://dashboard.render.com/](https://dashboard.render.com/) and log in to your account.

### 2. Create a PostgreSQL Service (Recommended)

1. Click "New" and select "PostgreSQL"
2. Give a name to the database (e.g., `cs2-valuation-db`)
3. Select the plan (the free plan is sufficient for testing)
4. Click "Create Database"
5. **Important**: Note the connection URL (`DATABASE_URL`) that will be displayed after creation

**Alternative**: If you already have an external PostgreSQL database (Supabase, etc.), you can use its credentials.

### 3. Create a new Web Service

1. Click "New" and select "Web Service"
2. Connect the Git repository with the API code
3. Give a name to the service (recommended: `cs2-valuation-api`)
4. Set the **Root Directory** as `cotacao_cs2` (or the directory where the `main.py` file is located)

### 4. Configure the environment

- **Environment**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 120 --keep-alive 120 main:app -b 0.0.0.0:$PORT`
- **Python Version**: `3.11.0` (or desired version)
- Select the appropriate plan for your needs (the free plan is sufficient for testing)

### 5. Configure environment variables

In the "Environment Variables" panel, add the following variables:

#### Database Configuration Options:

**Option 1: Neon.tech (Recommended)**
- `DATABASE_URL`: Complete PostgreSQL connection URL from Neon.tech
  - Example: `postgresql://neondb_owner:password@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require`
  - See [NEON_DATABASE.md](NEON_DATABASE.md) for detailed setup instructions

**Option 2: Render PostgreSQL**
- Render automatically creates the `DATABASE_URL` variable when you link the PostgreSQL service to the web service
- To link: In the web service, go to "Environment" > "Link Resource" > Select your PostgreSQL database

**Option 3: External PostgreSQL**
- `DATABASE_URL`: Complete PostgreSQL connection URL
  - Example: `postgresql://user:password@host:port/database?sslmode=prefer`
- Or use separate components:
  - `DB_HOST`: Database host
  - `DB_PORT`: Port (usually 5432)
  - `DB_NAME`: Database name
  - `DB_USER`: Database user
  - `DB_PASSWORD`: Database password

#### Other optional variables:
- `JWT_SECRET_KEY`: A long and secure string for JWT token signing (recommended)
- `PYTHON_VERSION`: `3.11.0` (already configured in render.yaml)

### 6. Additional settings

- In "Advanced", enable "Auto-Deploy" if you want Render to automatically update when there are new commits
- Configure the **Health Check Path** as `/healthcheck` (optional, but recommended)

### 7. Create the service

Click "Create Web Service" and wait for the deployment. The process may take a few minutes.

### 8. Initialize the database

After successful deployment, you need to initialize the database tables:

1. Access your service URL: `https://your-service.onrender.com`
2. Access the initialization endpoint (requires admin key):
   ```
   https://your-service.onrender.com/api/db/init?admin_key=YOUR_ADMIN_KEY
   ```
   Or configure the `ADMIN_KEY` variable on Render and use that value.

**Alternative**: Run the script locally pointing to Render's database:
```bash
export DATABASE_URL="your-render-url"
python migrate_db.py
```

### 9. Testing the API

After deployment, you can access the API through the URL provided by Render, usually in the format:
`https://your-service.onrender.com`

Verify that the API is working correctly by accessing:
- `https://your-service.onrender.com/api/status`
- `https://your-service.onrender.com/healthcheck`

### 10. Update configurations

1. **CORS**: Add your Render service URL to the allowed origins list in `main.py`:
   ```python
   ALLOWED_ORIGINS = [
       # ... other origins ...
       "https://your-service.onrender.com",  # Add here
   ]
   ```

2. **Frontend**: Update the API URL in the frontend (`api.html` file):
   ```javascript
   const API_BASE_URL = isLocalhost 
                        ? 'http://localhost:8000'  // Development environment
                        : 'https://your-service.onrender.com';  // Production environment
   ```

## Troubleshooting

If you encounter problems during deployment, check:

1. **Render Logs**: In the Render dashboard, access your service logs to identify errors
2. **CORS Settings**: Verify that all necessary origins are configured in `main.py`
3. **Environment Variables**: Confirm that all necessary environment variables have been configured, especially `DATABASE_URL`
4. **Database Issues**: 
   - Check if the PostgreSQL service is active
   - Confirm credentials are correct
   - If using external database, verify it allows connections from Render (IP whitelist)
5. **Port**: Make sure the `Procfile` or `startCommand` uses `$PORT` and not a fixed port

## Important Notes

- **Free Plan**: Render's free plan shuts down the service after periods of inactivity (15 minutes), which can cause slowness on the first request after a period without use (cold start)
- **Steam Authentication**: Confirm that callback URLs for Steam authentication are correctly configured for Render's URL
- **Database**: The free PostgreSQL plan on Render has space and connection limitations. For production, consider a paid plan
- **Timeout**: Render has a 30-second timeout for HTTP requests on the free plan. Longer requests may fail
- **Health Check**: The `/healthcheck` endpoint is used by Render to verify if the service is working

## Configuration Files

The project includes the following files for Render deployment:

- `render.yaml`: Web service configuration (optional, can be configured via dashboard)
- `Procfile`: Service startup command
- `Dockerfile`: Alternative for Docker deployment (not necessary if using native build)
- `migrate_db.py`: Script to initialize the database
