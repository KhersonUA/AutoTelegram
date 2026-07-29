import sqlite3
from pathlib import Path

DATABASE_FILE = Path(__file__).parent / "cars.db"


def create_database():
    with sqlite3.connect(DATABASE_FILE) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS adverts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.commit()


def advert_exists(url):
    with sqlite3.connect(DATABASE_FILE) as connection:
        result = connection.execute(
            "SELECT id FROM adverts WHERE url = ?",
            (url,),
        ).fetchone()
    return result is not None


def save_advert(title, url):
    with sqlite3.connect(DATABASE_FILE) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO adverts (title, url) VALUES (?, ?)",
            (title, url),
        )
        connection.commit()


def get_adverts_count():
    with sqlite3.connect(DATABASE_FILE) as connection:
        result = connection.execute(
            "SELECT COUNT(*) FROM adverts"
        ).fetchone()
    return result[0]


def database_is_empty():
    return get_adverts_count() == 0


def get_setting(key, default=None):
    with sqlite3.connect(DATABASE_FILE) as connection:
        result = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
    return default if result is None else result[0]


def set_setting(key, value):
    with sqlite3.connect(DATABASE_FILE) as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )
        connection.commit()


if __name__ == "__main__":
    create_database()
    print("База данных успешно создана.")
    print(f"Файл базы: {DATABASE_FILE}")
    print(f"Объявлений в базе: {get_adverts_count()}")
