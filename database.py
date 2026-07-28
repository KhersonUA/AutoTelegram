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
        connection.commit()


def advert_exists(url):
    with sqlite3.connect(DATABASE_FILE) as connection:
        result = connection.execute(
            """
            SELECT id
            FROM adverts
            WHERE url = ?
            """,
            (url,),
        ).fetchone()

    return result is not None


def save_advert(title, url):
    with sqlite3.connect(DATABASE_FILE) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO adverts (title, url)
            VALUES (?, ?)
            """,
            (title, url),
        )
        connection.commit()


def get_adverts_count():
    with sqlite3.connect(DATABASE_FILE) as connection:
        result = connection.execute(
            """
            SELECT COUNT(*)
            FROM adverts
            """
        ).fetchone()

    return result[0]


def database_is_empty():
    return get_adverts_count() == 0


if __name__ == "__main__":
    create_database()

    print("База данных успешно создана.")
    print(f"Файл базы: {DATABASE_FILE}")
    print(f"Объявлений в базе: {get_adverts_count()}")