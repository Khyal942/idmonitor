import os
import asyncio
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN
from sql import create_db, add_user, update_user, get_users, delete_user
import random

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

Telegram = Client(
    "Telegram",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

monitoring_active = False
delete_on_command = False
chat_ids = [1716718736, 1656690215]

create_db()  # Ensure this is called to create the database

async def send_notification(chat_id, message):
    try:
        await Telegram.send_message(chat_id, message)
    except Exception as e:
        print(f"Error sending notification: {str(e)}")

# Set to keep track of users who have been notified about missing usernames
notified_users = set()

async def monitor_usernames(chat_id):
    global notified_users
    try:
        while monitoring_active:
            users = get_users(chat_id)  # Get users for the specific chat_id
            for user_id, username, last_known_username, not_found in users:
                try:
                    user_info = await Telegram.get_chat(user_id)
                    current_username = user_info.username if user_info.username else None
                    user_name = user_info.first_name or ""
                    if user_info.last_name:
                        user_name += " " + user_info.last_name

                    if current_username is None:
                        if user_id not in notified_users:
                            print(f"User ID {user_id} ({user_name}) currently does not have a username set.")
                            notified_users.add(user_id)
                            await send_notification(chat_id, f"User ID {user_id} ({user_name}) currently does not have a username set.")
                        update_user(user_id, None, True)
                        continue

                    if current_username != last_known_username:
                        old_username = last_known_username
                        print(f'User ID {user_id} ({user_name}) changed username from @{old_username} to @{current_username}.')
                        update_user(user_id, current_username, False)
                        await send_notification(chat_id, f'User ID {user_id} ({user_name}) changed username from @{old_username} to @{current_username}.')

                except Exception as user_error:
                    error_message = str(user_error)
                    if "FLOOD_WAIT" in error_message:
                        wait_time = 0
                        try:
                            wait_time = int(error_message.split('FLOOD_WAIT_')[1].split(' ')[0])
                        except (ValueError, IndexError):
                            print(f"Error parsing wait time from error message: {error_message}")
                        if wait_time > 0:
                            print(f"Rate limit exceeded. Waiting for {wait_time} seconds.")
                            await asyncio.sleep(wait_time)
                    elif "USERNAME_NOT_OCCUPIED" in error_message:
                        print(f"Error checking username for user ID {user_id}: Username not occupied.")
                        update_user(user_id, last_known_username, True)
                    elif "USERNAME_INVALID" in error_message:
                        print(f"Error checking username for user ID {user_id}: Username is invalid.")
                        update_user(user_id, last_known_username, True)
                    else:
                        print(f"Error checking username for user ID {user_id}: {error_message}")

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
    chat_id = update.chat.id  # Get the chat ID where the command was issued
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

    users_to_add = update.command[1:]  # Get the list of usernames/user IDs

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

            chat_id = update.chat.id  # Get the chat ID where the command was issued
            add_user(user_id, username, username, False, chat_id)
            await update.reply_text(f"User @{username or user_id} added with ID: `{user_id}`")

        except Exception as e:
            await update.reply_text(f"Error adding user {user}: {e}")


@Telegram.on_message(filters.private & filters.command(["showlist"]))
async def show_user_list(_, update):
    user_list_text = "List of added users:\n"
    for chat_id in chat_ids:
        users = get_users(chat_id=chat_id)  # Fetch users from the database for the given chat ID
        if users:
            user_list = [f"Chat ID: {chat_id}, ID: {user_id}, Username: @{last_known_username or 'None'}" for user_id, username, last_known_username, not_found in users]

            user_list_text += "\n".join(user_list) + "\n\n"
        else:
            user_list_text += f"No users added for chat ID {chat_id}.\n\n"

    # Maximum message length for Telegram
    max_message_length = 4096

    # Split the user list into chunks that fit within the max message length
    messages = []
    current_message = ""

    for line in user_list_text.split("\n"):
        if len(current_message) + len(line) + 1 > max_message_length:
            messages.append(current_message)
            current_message = line + "\n"
        else:
            current_message += line + "\n"

    # Append the last message
    if current_message:
        messages.append(current_message)

    # Send all the messages
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
    try:
        if len(update.command) < 2:
            await update.reply_text("Please provide a user ID or username. Usage: /delete user_id_or_username")
            return

        user_id_or_username = update.command[1].strip('@')  # Remove the @ symbol if present
        user_id_to_delete = None

        if user_id_or_username.isdigit():
            user_id_to_delete = int(user_id_or_username)
        else:
            username_to_delete = user_id_or_username
            # Debugging: Print the username to be deleted
            print(f"Trying to delete username: '{username_to_delete}'")
            found = False
            for user in get_users():
                stored_user_id, stored_username, _, _ = user
                # Debugging: Print the stored username
                print(f"Stored username: '{stored_username}'")
                if stored_username == username_to_delete:
                    user_id_to_delete = stored_user_id
                    found = True
                    break

            if not found:
                await update.reply_text(f"No user found with username `{username_to_delete}`.")
                return

        if user_id_to_delete:
            delete_user(user_id_to_delete)
            await update.reply_text(f"User with ID `{user_id_to_delete}` deleted successfully.")
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

    # Define the file path in the current directory
    file_path = os.path.join(os.getcwd(), "added_users_list.txt")

    # Write the content to the text file
    with open(file_path, "w") as file:
        file.write(user_list_text)

    # Send the file
    await update.reply_document(file_path)

    # Clean up the file after sending
    os.remove(file_path)


@Telegram.on_message(filters.private & filters.command(["deletenotfound"]))
async def delete_user_command(_, update):
    users = get_users()
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
