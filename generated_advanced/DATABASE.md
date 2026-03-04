# Database Schema & Migrations

## PostgreSQL Setup

```sql
CREATE DATABASE mortgage_uw;
CREATE USER mortgage_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE mortgage_uw TO mortgage_user;
```

## Migrations

Using Alembic for schema management:

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Core Tables

Each module generates its own tables. See module documentation for details.

### Audit Trail

All tables include:
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp
- `changed_by` - User who made change (for audit)

### Financial Values

All monetary amounts use `DECIMAL(19,4)` precision never float.

## Backups

```bash
# Backup
pg_dump mortgage_uw > backup_$(date +%Y%m%d).sql

# Restore
psql mortgage_uw < backup_20240115.sql
```
