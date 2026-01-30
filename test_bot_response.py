"""Quick bot test."""
import requests
import os
from dotenv import load_dotenv
import time

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Send test message
print("Sending test message to Telegram...")
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
response = requests.post(url, json={
    "chat_id": CHAT_ID,
    "text": "🧪 Bot test - Play Yesterday by The Beatles"
})
print(f"Message sent: {response.ok}")

# Wait for bot to process
time.sleep(5)

# Check bot logs
print("\n=== Bot Logs (last 10 lines) ===")
with open("bot_err.log", "r", encoding="utf-8") as f:
    lines = f.readlines()
    for line in lines[-10:]:
        print(line.strip())
