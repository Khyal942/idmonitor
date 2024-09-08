from flask import Flask, render_template, redirect, url_for
import subprocess

# Flask app initialization
app = Flask(__name__)

# Global variable to keep track of the subprocess
bot_process = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start():
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        bot_process = subprocess.Popen(["python", "bot.py"])
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop():
    global bot_process
    if bot_process is not None:
        bot_process.terminate()
        bot_process = None
    return redirect(url_for('index'))

if __name__ == "__main__":
    # Remove or comment out the app.run line for deployment
    pass
