import os
import sqlite3

# Путь к файлу базы данных
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "cart.db")

# Создаём папку, если её нет
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)


# Функция для подключения к БД
def get_db_connection():
    return sqlite3.connect(DB_PATH)


# Создание таблиц (пользователи и корзина)
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Таблица корзины (теперь хранит только user_id и product_id)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()


# Функция добавления пользователя
def add_user(user_id, username, first_name, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET 
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name
    """, (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()


# Функция добавления товара в корзину по product_id
def add_to_cart(user_id, product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cart (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
    conn.commit()
    conn.close()


# Функция получения списка product_id в корзине пользователя
def get_cart(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM cart WHERE user_id = ?", (user_id,))
    items = [row[0] for row in cursor.fetchall()]
    conn.close()
    return items


# Функция удаления товара из корзины по cart_id
def remove_from_cart(user_id, product_id):
    """
    Удаляем товар из корзины пользователя по user_id + product_id.
    """
    print(f"Удаляем у пользователя {user_id} товар {product_id}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM cart WHERE user_id = ? AND product_id = ?",
        (user_id, product_id)
    )
    conn.commit()
    conn.close()


# Функция очистки корзины пользователя
def clear_cart(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# Функция получения количества товаров в корзине пользователя
def get_cart_count(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cart WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# Функция получения количества пользователей и списка их id
def get_users_info():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return len(users), users  # Возвращает количество пользователей и их id


# Инициализация базы данных
create_tables()

# Примеры вызова новых функций
# print(get_cart_count(1338143348))  # Получение количества товаров в корзине
# print(get_users_info())  # Получение количества пользователей и списка их id
