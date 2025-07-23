import os
import logging
import base64
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
load_dotenv()

# --- Flask web server for Render keep-alive ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Get the token from environment variable
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# --- In-memory file database ---
file_database = {}
file_counter = 0
# -----------------------------

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global file_counter
    if not update.message:
        return

    file_id = None
    file_type = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = "photo"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
    elif update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
    else:
        return

    file_counter += 1
    file_key = f"file_{file_counter}"
    file_database[file_key] = {"id": file_id, "type": file_type}
    encoded_key = base64.urlsafe_b64encode(file_key.encode()).decode()
    bot_username = (await context.bot.get_me()).username
    deep_link = f"https://t.me/{bot_username}?start={encoded_key}"
    await update.message.reply_text(
        f"✅ Deep link generated!\n\nShare this link to give others access to the file:\n{deep_link}"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            encoded_key = context.args[0]
            decoded_key = base64.urlsafe_b64decode(encoded_key).decode()
            file_data = file_database.get(decoded_key)
            if file_data:
                file_id = file_data["id"]
                file_type = file_data["type"]
                await update.message.reply_text("Sending you the file...")
                if file_type == "photo":
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
                elif file_type == "document":
                    await context.bot.send_document(chat_id=update.effective_chat.id, document=file_id)
                elif file_type == "video":
                    await context.bot.send_video(chat_id=update.effective_chat.id, video=file_id)
            else:
                await update.message.reply_text("Sorry, this link is invalid or has expired.")
        except Exception as e:
            logger.error(f"Error processing deep link: {e}")
            await update.message.reply_text("This link appears to be broken.")
    else:
        await update.message.reply_text("Hello! Send me a file to generate a shareable deep link.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("!!! ERROR: TELEGRAM_BOT_TOKEN not found. !!!")
        return
    print("Bot is starting with deep link logic...")
    # Start Flask in a separate thread for Render keep-alive
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    # Start the Telegram bot as usual
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO, file_handler))
    application.run_polling()

if __name__ == '__main__':
    main() 
