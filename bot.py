import os
import asyncio
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN
from sql import create_db, add_user, update_user, get_users, delete_user_by_username_or_id, delete_user
import random
import time

# Initialize environment variables
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Database file (ensure this path is correct)
DATABASE_FILE = os.environ.get("DATABASE_FILE", "users_data.db")

# Initialize the Telegram client
Telegram = Client("Telegram", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Ensure the database is created
create_db()

# Global variables
monitoring_active = False
chat_ids = [1716718736, 1656690215]
notified_users = {}
last_notification_time = {}

async def send_notification(chat_id, message):
    try:
        await Telegram.send_message(chat_id, message)
    except Exception as e:
        print(f"Error sending notification: {str(e)}")

async def monitor_usernames(chat_id):
    try:
        while monitoring_active:
            users = get_users(chat_id)
            current_time = time.time()
            for user_id, username, last_known_username, not_found in users:
                try:
                    await asyncio.sleep(0.5)
                    user_info = await Telegram.get_chat(user_id)
                    current_username = user_info.username if user_info.username else None
                    user_name = user_info.first_name or ""
                    if user_info.last_name:
                        user_name += " " + user_info.last_name

                    if current_username is None:
                        if user_id not in notified_users or notified_users[user_id] != "missing":
                            notified_users[user_id] = "missing"
                            await send_notification(chat_id, f"User ID {user_id} ({user_name}) currently does not have a username set.")
                        update_user(user_id, None, True)
                    elif current_username != last_known_username:
                        if (user_id not in notified_users or notified_users[user_id] != current_username):
                            await send_notification(chat_id, f'User ID {user_id} ({user_name}) changed username from @{last_known_username} to @{current_username}.')
                            last_notification_time[user_id] = current_time
                            notified_users[user_id] = current_username
                        update_user(user_id, current_username, False)
                except Exception as user_error:
                    error_message = str(user_error)
                    if "FLOOD_WAIT" in error_message:
                        wait_time = int(error_message.split('FLOOD_WAIT_')[1].split(' ')[0]) if 'FLOOD_WAIT_' in error_message else 0
                        if wait_time > 0:
                            await asyncio.sleep(wait_time)
                    elif "USERNAME_NOT_OCCUPIED" in error_message or "USERNAME_INVALID" in error_message:
                        update_user(user_id, last_known_username, True)
            await asyncio.sleep(random.uniform(60, 80))
    except Exception as e:
        await send_notification(chat_id, f"Error during monitoring: {str(e)}")
        await asyncio.sleep(80)

async def restart_monitoring():
    global monitoring_active
    while True:
        if monitoring_active:
            monitoring_active = False
            await asyncio.sleep(5)
            monitoring_active = True
            for chat_id in chat_ids:
                asyncio.ensure_future(monitor_usernames(chat_id))
        await asyncio.sleep(43200)  # 12 hours

@Telegram.on_message(filters.private & filters.command(["start"]))
async def start_monitoring(_, update):
    global monitoring_active
    monitoring_active = True
    chat_id = update.chat.id
    await update.reply_text("Monitoring started. I will notify you of any username changes.")
    await send_notification(chat_id, "Monitoring started.")
    for chat_id in chat_ids:
        asyncio.ensure_future(monitor_usernames(chat_id))
    asyncio.ensure_future(restart_monitoring())

@Telegram.on_message(filters.private & filters.command(["stop"]))
async def stop_monitoring(_, update):
    global monitoring_active
    monitoring_active = False
    await update.reply_text("Monitoring stopped.")
    for chat_id in chat_ids:
        await send_notification(chat_id, "Monitoring stopped.")

@Telegram.on_message(filters.private & filters.command(["adduser"]))
async def add_user_command(_, update):
    if len(update.command) < 2:
        await update.reply_text("Please provide at least one username or user ID. Usage: /adduser @username1 6707409905 ...")
        return

    users_to_add = update.command[1:]
    for user in users_to_add:
        user = user.strip('@')
        try:
            if user.isdigit():
                user_id = int(user)
                user_info = await Telegram.get_chat(user_id)
                username = user_info.username if user_info.username else None
            else:
                username = user
                user_info = await Telegram.get_chat(username)
                user_id = user_info.id

            chat_id = update.chat.id

            existing_users = get_users(chat_id=chat_id)
            if any(user_id == existing_user_id for existing_user_id, _, _, _ in existing_users):
                await update.reply_text(f"User with ID `{user_id}` already exists.")
            else:
                add_user(user_id, username, username, False, chat_id)
                await update.reply_text(f"User @{username or user_id} added with ID: `{user_id}`")
        except Exception as e:
            await update.reply_text(f"Error adding user {user}: {e}")

@Telegram.on_message(filters.private & filters.command(["showlist"]))
async def show_user_list(_, update):
    user_list_text = "List of added users:\n"
    for chat_id in chat_ids:
        users = get_users(chat_id=chat_id)
        if users:
            user_list = [f"Chat ID: {chat_id}, ID: {user_id}, Username: @{last_known_username or 'None'}" for user_id, username, last_known_username, not_found in users]
            user_list_text += "\n".join(user_list) + "\n\n"
        else:
            user_list_text += f"No users added for chat ID {chat_id}.\n\n"

    max_message_length = 4096
    messages = []
    current_message = ""
    for line in user_list_text.split("\n"):
        if len(current_message) + len(line) + 1 > max_message_length:
            messages.append(current_message)
            current_message = line + "\n"
        else:
            current_message += line + "\n"
    if current_message:
        messages.append(current_message)
    for msg in messages:
        await update.reply_text(msg)

@Telegram.on_message(filters.private & filters.command(["getid"]))
async def get_user_id(_, update):
    if len(update.command) < 3:
        await update.reply_text("Please provide a chat ID and a username. Usage: /getid chat_id @username")
        return

    chat_id = int(update.command[1])
    username = update.command[2].strip('@')
    try:
        user_id = None
        for user in get_users(chat_id=chat_id):
            if user[1] == username:
                user_id = user[0]
                break
        if user_id:
            await update.reply_text(f"The user ID for @{username} is: `{user_id}`")
        else:
            await update.reply_text(f"User @{username} not found in chat ID {chat_id}. Use /adduser to add them.")
    except Exception as e:
        await update.reply_text(f"Error: {e}")

@Telegram.on_message(filters.private & filters.command(["delete"]))
async def delete_user_command(_, update):
    chat_id = update.chat.id
    try:
        if len(update.command) < 2:
            await update.reply_text("Please provide a user ID or username. Usage: /delete user_id_or_username")
            return

        user_id_or_username = update.command[1].strip('@')
        user_id_to_delete = None
        last_known_username_to_delete = None

        if user_id_or_username.isdigit():
            user_id_to_delete = int(user_id_or_username)
        else:
            last_known_username_to_delete = user_id_or_username

        user_exists = False
        for user in get_users(chat_id):
            stored_user_id, stored_username, stored_last_known_username, _ = user
            if stored_last_known_username == last_known_username_to_delete or stored_user_id == user_id_to_delete:
                user_exists = True
                break

        if user_exists:
            delete_user_by_username_or_id(last_known_username_to_delete, chat_id, user_id_to_delete)
            await update.reply_text(f"User `{user_id_or_username}` deleted successfully.")
        else:
            await update.reply_text(f"No user found with ID or username `{user_id_or_username}`.")
    except Exception as e:
        await update.reply_text(f"Error: {e}")

@Telegram.on_message(filters.private & filters.command(["getlist"]))
async def get_user_list_file(_, update):
    user_list_text = ""
    for chat_id in chat_ids:
        users = get_users(chat_id=chat_id)
        if users:
            user_list_text += f"Chat ID: {chat_id}\n"
            user_list = [f"@{username or 'None'}: {user_id}" for user_id, username, _, _ in users]
            user_list_text += "\n".join(user_list) + "\n\n"
        else:
            user_list_text += f"No users added for chat ID {chat_id}.\n\n"

    if user_list_text.strip() == "":
        await update.reply_text("No users added. Use /adduser to add users.")
        return

    file_path = os.path.join(os.getcwd(), "added_users_list.txt")
    with open(file_path, "w") as file:
        file.write(user_list_text)

    await update.reply_document(file_path)
    os.remove(file_path)

@Telegram.on_message(filters.private & filters.command(["deletenotfound"]))
async def delete_not_found_users(_, update):
    chat_id = update.chat.id
    users = get_users(chat_id)
    for user_id, username, last_known_username, not_found in users:
        if not_found or last_known_username is None:
            delete_user(user_id)
    await update.reply_text("Usernames not found deleted successfully.")

# Start monitoring for all chat IDs
for chat_id in chat_ids:
    asyncio.ensure_future(monitor_usernames(chat_id))

if __name__ == "__main__":
    print("Bot is live.")
    Telegram.run()
