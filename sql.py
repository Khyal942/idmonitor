import sqlite3

def create_db():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        last_known_username TEXT,
        not_found BOOLEAN
    )''')
    conn.commit()
    conn.close()

def add_chat_id_column():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    # Check if the chat_id column already exists
    c.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in c.fetchall()]
    if 'chat_id' not in columns:
        c.execute('ALTER TABLE users ADD COLUMN chat_id INTEGER')
    conn.commit()
    conn.close()

# Create the database and ensure the table exists
create_db()

# Add the chat_id column if it doesn't exist
add_chat_id_column()

def add_user(user_id, username, last_known_username, not_found, chat_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''
    INSERT OR REPLACE INTO users (user_id, username, last_known_username, not_found, chat_id)
    VALUES (?, ?, ?, ?, ?)''', (user_id, username, last_known_username, not_found, chat_id))
    conn.commit()
    conn.close()

def update_user(user_id, last_known_username, not_found):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''UPDATE users SET last_known_username = ?, not_found = ? WHERE user_id = ?''',
              (last_known_username, not_found, user_id))
    conn.commit()
    conn.close()

def get_users(chat_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''
    SELECT user_id, username, last_known_username, not_found FROM users WHERE chat_id = ?
    ''', (chat_id,))
    users = c.fetchall()
    conn.close()
    return users

def delete_user(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''DELETE FROM users WHERE user_id = ?''', (user_id,))
    conn.commit()
    conn.close()
