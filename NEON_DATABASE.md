# Neon.tech Database Configuration

This project uses PostgreSQL database hosted on [Neon.tech](https://neon.tech/).

## Connection String

The connection string for the Neon.tech database is:

```
postgresql://neondb_owner:npg_SLMYc7bVQ1KR@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## Configuration

### Local Development

1. Create a `.env` file in the project root (copy from `.env.example` if available)
2. Add the `DATABASE_URL` environment variable:

```bash
DATABASE_URL=postgresql://neondb_owner:npg_SLMYc7bVQ1KR@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

### Render Deployment

1. Go to your Render dashboard
2. Select your web service
3. Go to "Environment" tab
4. Add the following environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: `postgresql://neondb_owner:npg_SLMYc7bVQ1KR@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require`

### Alternative: Separate Components

If you prefer to use separate environment variables instead of the connection string:

```bash
DB_HOST=ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech
DB_PORT=5432
DB_NAME=neondb
DB_USER=neondb_owner
DB_PASSWORD=npg_SLMYc7bVQ1KR
```

**Note**: When using separate components, SSL mode will be automatically set to `require` by the application.

## Database Initialization

After configuring the connection string, initialize the database tables:

### Option 1: Via API Endpoint

```bash
curl "https://your-service.onrender.com/api/db/init?admin_key=YOUR_ADMIN_KEY"
```

### Option 2: Via Migration Script

```bash
export DATABASE_URL="postgresql://neondb_owner:npg_SLMYc7bVQ1KR@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
python migrate_db.py
```

## Testing Connection

You can test the connection using psql:

```bash
psql 'postgresql://neondb_owner:npg_SLMYc7bVQ1KR@ep-icy-hill-aemvtr7r-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
```

Or using the host directly:

```bash
psql -h pg.neon.tech
```

## SSL Configuration

The Neon.tech database requires SSL connections with:
- `sslmode=require`: SSL connection is required
- `channel_binding=require`: Channel binding is required for additional security

These parameters are already included in the connection string and will be used automatically by the application.

## Troubleshooting

### Connection Issues

1. **SSL Error**: Ensure `sslmode=require` is in your connection string
2. **Channel Binding Error**: Ensure `channel_binding=require` is in your connection string
3. **Timeout**: Check if the Neon.tech service is active and accessible
4. **Authentication**: Verify credentials are correct

### Connection Pooling

Neon.tech uses connection pooling. The connection string includes `-pooler` in the hostname, which enables connection pooling for better performance.

## Notes

- The database uses connection pooling for better performance
- SSL is required for all connections
- Channel binding provides additional security
- The application will automatically retry with different SSL modes if the initial connection fails

