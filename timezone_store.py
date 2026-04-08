import os
import psycopg2
import psycopg2.extras
import pytz

def _get_conn():
    # Railway private networking: use individual params to avoid DNS issues with internal URLs
    return psycopg2.connect(
        host=os.getenv("PGHOST", "postgres"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "railway"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD"),
    )


def init_db() -> None:
    """Create the timezones table if it doesn't exist. Called once on bot startup."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_timezones (
                    user_id TEXT PRIMARY KEY,
                    timezone TEXT NOT NULL
                )
            """)


def get_user_tz(user_id: int) -> pytz.BaseTzInfo | None:
    tz_str = get_user_tz_str(user_id)
    if tz_str is None:
        return None
    return pytz.timezone(tz_str)


def get_user_tz_str(user_id: int) -> str | None:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timezone FROM user_timezones WHERE user_id = %s",
                (str(user_id),)
            )
            row = cur.fetchone()
            return row[0] if row else None


def set_user_tz(user_id: int, tz_string: str) -> None:
    pytz.timezone(tz_string)  # raises UnknownTimeZoneError if invalid
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_timezones (user_id, timezone)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET timezone = EXCLUDED.timezone
            """, (str(user_id), tz_string))
