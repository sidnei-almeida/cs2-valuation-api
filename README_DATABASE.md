# Database Cache System for Elite Skins API

## Overview

This system implements a database cache for CS2 skin prices, significantly reducing requests to external APIs and improving application performance and reliability.

### Main Features

- **PostgreSQL Cache**: Stores skin prices locally to avoid multiple requests for the same skin
- **Automatic weekly updates**: Job that automatically updates the oldest prices in the database
- **Management API**: Endpoints to view statistics and force updates
- **PostgreSQL Support**: Full support for PostgreSQL database for production deployment

## How It Works

1. When a skin price is requested, the system:
   - First checks the memory cache (for repeated queries in the same session)
   - Then queries the PostgreSQL database
   - If not found or price is outdated, performs scraping (as before)
   - Stores the result in both memory cache and database

2. A weekly job runs in the background to update the oldest prices in the database, even when there are no active requests for those skins.

## Database Structure

### `skin_prices` Table
- `id`: Unique record ID
- `market_hash_name`: Skin name on Steam market
- `price`: Current skin price
- `currency`: Currency code
- `app_id`: Steam application ID
- `last_updated`: Date/time of last price update
- `last_scraped`: Date/time of last scraping
- `update_count`: Update counter

### `metadata` Table
- `key`: Metadata key
- `value`: Metadata value
- `updated_at`: Date/time of last update

## How to Use

### Management via API

The following endpoints have been added:

1. `/api/status`: Now includes database statistics
   ```json
   {
     "status": "online",
     "components": {
       "database": {
         "total_skins": 1245,
         "recently_updated": 236,
         "average_price": 42.80
       }
     }
   }
   ```

2. `/db/stats`: Returns detailed database statistics (requires authentication)
   ```json
   {
     "database": {
       "total_skins": 1245,
       "average_price": 42.80,
       "recently_updated": 236,
       "last_update": "2023-10-28T15:32:47"
     },
     "scheduler": {
       "last_update": "2023-10-25T03:00:12",
       "next_update": "2023-11-01T03:00:00"
     }
   }
   ```

3. `/db/update`: Forces immediate price update (requires authentication)
   - Parameter `max_items`: Maximum number of items to update (default: 100)

### Database Initialization

When deploying to production:

1. Configure the `DATABASE_URL` environment variable in your production environment on Render
2. Run the migration script once:
   ```bash
   python migrate_db.py
   ```
   Or access the initialization endpoint:
   ```
   https://your-service.onrender.com/api/db/init?admin_key=YOUR_ADMIN_KEY
   ```

## Configuration

Main settings can be adjusted:

1. **Update Period:** Default is weekly (Monday at 3 AM)
   - Can be changed in `main.py` in the `startup_event()` function

2. **Items per Update:** Default is 100 skins per execution
   - Defined by the `UPDATE_BATCH_SIZE` constant in `utils/price_updater.py`

3. **Cache Validity Time:** Default is 7 days
   - Can be changed in the `get_skin_price()` function in `utils/database.py`

## Benefits

- **Less API usage:** Drastically reduces requests to external APIs
- **Better performance:** Faster responses for users
- **Greater reliability:** System works even if external API is unavailable
- **Resource savings:** Less real-time processing

## Fallback System

The API has a fallback system that allows operation even in case of PostgreSQL connection failure:

1. When unable to connect to the database, it uses in-memory storage
2. Data is synchronized when the connection is restored
3. This ensures high API availability even during temporary issues

## Troubleshooting

### Database is not being updated
- Check if the scheduler is running: `/db/stats` should show the next update
- You can force an immediate update with `/db/update`

### Errors during PostgreSQL connection
- Verify that the `DATABASE_URL` variable is correct
- Confirm that PostgreSQL is accessible from your server
- Check if there are SSL connection issues (the system tries different SSL modes automatically)
