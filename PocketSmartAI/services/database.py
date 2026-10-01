import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "pocketsmart.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as db:

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                input_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY(user_id)
                REFERENCES users(id)
            )
            """
        )

        db.commit()


def create_user(
    username: str,
    email: str,
    password_hash: str
):
    with get_connection() as db:

        cursor = db.execute(
            """
            INSERT INTO users
            (
                username,
                email,
                password_hash,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                email,
                password_hash,
                datetime.now(timezone.utc).isoformat()
            )
        )

        db.commit()

        return cursor.lastrowid


def get_user_by_username(username: str):
    with get_connection() as db:

        row = db.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if row:
            return dict(row)

        return None


def get_user_by_id(user_id: int):
    with get_connection() as db:

        row = db.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if row:
            return dict(row)

        return None


def save_recommendation(
    user_id: int,
    category: str,
    input_data: dict,
    result: dict
):
    with get_connection() as db:

        cursor = db.execute(
            """
            INSERT INTO recommendations
            (
                user_id,
                category,
                input_json,
                result_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                category,
                json.dumps(input_data),
                json.dumps(result),
                datetime.now(timezone.utc).isoformat()
            )
        )

        db.commit()

        return cursor.lastrowid


def list_recommendations(
    user_id: int,
    limit: int = 20
):
    with get_connection() as db:

        rows = db.execute(
            """
            SELECT *
            FROM recommendations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit)
        ).fetchall()

    results = []

    for row in rows:

        item = dict(row)

        item["input"] = json.loads(
            item.pop("input_json")
        )

        item["result"] = json.loads(
            item.pop("result_json")
        )

        results.append(item)

    return results


def get_recommendation(
    recommendation_id: int,
    user_id: int
):
    with get_connection() as db:

        row = db.execute(
            """
            SELECT *
            FROM recommendations
            WHERE id = ?
            AND user_id = ?
            """,
            (
                recommendation_id,
                user_id
            )
        ).fetchone()

    if not row:
        return None

    item = dict(row)

    item["input"] = json.loads(
        item.pop("input_json")
    )

    item["result"] = json.loads(
        item.pop("result_json")
    )

    return item