"""SQLite access for the products and orders tables in store.db."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "store.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def search_products(keyword: str, max_price: float | None = None, is_organic: bool | None = None) -> list[dict]:
    conn = _connect()
    cursor = conn.cursor()

    clauses = ["(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ?)"]
    like = f"%{keyword.lower()}%"
    params: list = [like, like, like]

    if max_price is not None:
        clauses.append("price <= ?")
        params.append(max_price)

    if is_organic is not None:
        clauses.append("is_organic = ?")
        params.append(1 if is_organic else 0)

    query = f"SELECT id, name, category, price, description, is_organic FROM products WHERE {' AND '.join(clauses)} ORDER BY id"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_product(product_id: int) -> dict | None:
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, category, price, description, is_organic FROM products WHERE id = ?",
        (product_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def place_order(product_id: int) -> dict:
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"No product with id {product_id}")

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (product_id, product_name, price) VALUES (?, ?, ?)",
        (product["id"], product["name"], product["price"]),
    )
    conn.commit()
    order_id = cursor.lastrowid
    cursor.execute("SELECT id, product_id, product_name, price, ordered_at FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_orders() -> list[dict]:
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product_id, product_name, price, ordered_at FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
