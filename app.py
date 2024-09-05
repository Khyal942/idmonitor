import asyncio
from flask import Flask, request, jsonify
from bot import Telegram, start_monitoring, stop_monitoring  # Import your bot and relevant functions

app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is running via Flask!"

@app.route('/start_monitoring', methods=['POST'])
def start_bot_monitoring():
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        loop.create_task(Telegram.start())
    return jsonify({"status": "Bot monitoring started!"})

@app.route('/stop_monitoring', methods=['POST'])
def stop_bot_monitoring():
    stop_monitoring()
    return jsonify({"status": "Bot monitoring stopped!"})

@app.route('/status', methods=['GET'])
def get_status():
    status = "running" if Telegram.is_running else "stopped"
    return jsonify({"status": status})

async def run_flask():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, app.run, '0.0.0.0', 5000)

async def main():
    await asyncio.gather(
        Telegram.start(),  # This assumes Telegram.start() is an async function
        run_flask()
    )

if __name__ == "__main__":
    asyncio.run(main())
