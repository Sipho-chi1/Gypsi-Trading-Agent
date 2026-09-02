"""Initializes the local PostgreSQL database and applies schema."""
import asyncio
import asyncpg
from app.models.trade import SCHEMA_SQL

async def main():
    print("Connecting to PostgreSQL...")
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/postgres")
    
    # Check if gypsi database exists
    row = await conn.fetchrow("SELECT 1 FROM pg_database WHERE datname = 'gypsi'")
    if not row:
        print("Creating database 'gypsi'...")
        await conn.execute("CREATE DATABASE gypsi")
    else:
        print("Database 'gypsi' already exists.")

    # Create / update gypsi role
    user_row = await conn.fetchrow("SELECT 1 FROM pg_roles WHERE rolname = 'gypsi'")
    if not user_row:
        print("Creating user 'gypsi'...")
        await conn.execute("CREATE USER gypsi WITH PASSWORD 'gypsi' SUPERUSER")
    else:
        print("User 'gypsi' already exists.")
        await conn.execute("ALTER USER gypsi WITH PASSWORD 'gypsi'")
    
    await conn.close()

    print("Connecting to 'gypsi' database...")
    gypsi_conn = await asyncpg.connect("postgresql://gypsi:gypsi@localhost:5432/gypsi")
    print("Applying schema tables & indexes...")
    await gypsi_conn.execute(SCHEMA_SQL)
    print("Database tables initialized successfully!")
    await gypsi_conn.close()

if __name__ == "__main__":
    asyncio.run(main())
