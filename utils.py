import psycopg2
import os
from urllib.parse import urlparse
import json
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def serialize_photos(photos):
    if isinstance(photos, list):
        return json.dumps(photos, ensure_ascii=False)
    return photos


def parse_photos(photo_value):
    if not photo_value:
        return []

    try:
        parsed = json.loads(photo_value)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str) and item]
    except (json.JSONDecodeError, TypeError):
        pass

    return [photo_value]

def update_product_field(product_id, field, value):
    conn = get_connection()
    cur = conn.cursor()

    if field == "photo":
        value = serialize_photos(value)

    query = f"UPDATE products SET {field} = %s WHERE id = %s"
    cur.execute(query, (value, product_id))

    conn.commit()
    cur.close()
    conn.close()

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# 🛠 ИНИЦИАЛИЗАЦИЯ БД (Создаем таблицу, если её нет)
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT,
            description TEXT,
            price INTEGER,
            photo TEXT,
            category TEXT
        );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        date_day INTEGER,
        date_month INTEGER,
        description TEXT
    );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("База данных проверена/создана.")

# ➕ ДОБАВИТЬ ТОВАР
def add_product(name, description, price, photo, category):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (name, description, price, photo, category)
        VALUES (%s, %s, %s, %s, %s)
    """, (name, description, price, serialize_photos(photo), category))
    conn.commit()
    cur.close()
    conn.close()

# 📦 ПОЛУЧИТЬ ВСЕ ТОВАРЫ ПО КАТЕГОРИИ
def get_products_by_category(category):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, description, price, photo, category
        FROM products
        WHERE category=%s
        ORDER BY id
    """, (category,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    products = []
    for row in rows:
        photo_list = parse_photos(row[4])
        products.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "price": row[3],
            "photo": photo_list[0] if photo_list else None,
            "photos": photo_list,
            "category": row[5]
        })
    return products

# 🔍 ПОЛУЧИТЬ ОДИН ТОВАР ПО ID (для оформления заказа)
def get_product_by_id(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, description, price, photo, category
        FROM products
        WHERE id=%s
    """, (product_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        photo_list = parse_photos(row[4])
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "price": row[3],
            "photo": photo_list[0] if photo_list else None,
            "photos": photo_list,
            "category": row[5]
        }
    return None

# 🗑 УДАЛИТЬ ТОВАР
def delete_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()

def add_reminder(user_id, day, month, desc):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO reminders (user_id, date_day, date_month, description) VALUES (%s, %s, %s, %s)", 
                (user_id, day, month, desc))
    conn.commit()
    cur.close()
    conn.close()

