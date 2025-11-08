# Deploy on Railway

This guide describes how to deploy the Elite Skins CS2 API on Railway.

## Railway Configuration

1. Create an account on [Railway](https://railway.app/)
2. Start a new project by selecting "Deploy from GitHub"
3. Authorize Railway to access your repository and select the project repository
4. In the initial configuration, set the root directory as `cotacao_cs2`
5. Add a PostgreSQL service to your project by clicking "New" and selecting "Database" > "PostgreSQL"

## Environment Variables

Environment variables are already configured in the `railway.toml` file to use the public PostgreSQL connection:

| Variable Name | Value |
|---------------|-------|
| `DATABASE_URL` | `postgresql://postgres:PASSWORD@gondola.proxy.rlwy.net:10790/railway` |
| `DB_HOST` | `gondola.proxy.rlwy.net` |
| `DB_PORT` | `10790` |
| `DB_NAME` | `railway` |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | `PASSWORD` |
| `PORT` | `8080` (automatically set by Railway) |

**Important note**: We're using the public PostgreSQL endpoint (`gondola.proxy.rlwy.net`) instead of the internal one, as the internal endpoint may not resolve correctly in all Railway environments.

## How to Deploy

1. Via Railway CLI (recommended):
   ```bash
   # Install Railway CLI
   npm i -g @railway/cli
   
   # Login
   railway login
   
   # Start a project (or link to an existing one)
   railway init
   
   # Deploy (from the cotacao_cs2 folder)
   cd cotacao_cs2
   railway up
   ```

2. Or via Railway dashboard (simpler):
   - Connect your GitHub repository
   - Configure the `cotacao_cs2` directory as the source folder
   - Click "Deploy"

## Verify Status

After deployment, you can verify if the API is working by accessing the endpoint:

```
https://[your-railway-app].railway.app/api/status
```

## Troubleshooting

- **Database connection error**: 
  - Check if the PostgreSQL service is active on Railway
  - Confirm credentials are correct
  - Verify that the public endpoint `gondola.proxy.rlwy.net` is accessible
  - If the port or host changed, update them in `database.py` and `railway.toml`

- **Initialization error**: 
  - Check the logs in the Railway dashboard to identify the problem

- **CORS**: 
  - If there are CORS issues, verify that the frontend domain is in the allowed origins list in the `main.py` file

## Fallback System

The API has a fallback system that allows operation even in case of PostgreSQL connection failure:

1. When unable to connect to the database, it uses in-memory storage
2. Data is synchronized when the connection is restored
3. This ensures high API availability even during temporary issues

## Notes

- Railway offers integrated monitoring and logs to facilitate problem diagnosis
- Remember that Railway's free plan has a monthly usage limit ($5 credit)
- For better performance, consider using a region close to your users
