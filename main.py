import asyncio
import random
from typing import Final
import uuid
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import sqlite3, os

from utils import softmax, check_response, sample_word


TOKEN: Final = ""
BOT_USERNAME: Final = "@WortMerkenBot"
db_filename = 'wortmerken_new.db'


async def scheduled_task(context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = context.job.data['user_id']
    if context.application.user_data[user_id].get("chatting", False) or \
        context.application.user_data[user_id].get("wating_user", False) or \
        context.application.user_data[user_id].get("add_items", False):
        return
    
    print(user_id, context.application.user_data[user_id])
    
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM german_items WHERE user_id = ?", (user_id, ))
    rows = cursor.fetchall()
    conn.commit()
    conn.close()
    
    if len(rows) >= 5:
        context.application.user_data[user_id]['wating_user'] = True
        z = sample_word(user_id, db_filename=db_filename)
        context.application.user_data[user_id]['answer_guessing'] = z[0]
        await context.bot.send_message(chat_id=context.job.chat_id, 
                                       text=z[0])
    
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    cursor.execute(f"SELECT COUNT(*) FROM users WHERE tlgm_uid = ?", (user_id,))
    result = cursor.fetchone()
    
    if not result[0]:
        cursor.execute(f'''INSERT INTO users (tlgm_uid, username)
                        VALUES ('{user_id}', '{update.message.from_user.username}')''')
        
        print(f"User '{update.message.from_user.username}' inserted in db.")

    conn.commit()
    conn.close()

    await update.message.reply_text("Welcome to the WortMerken bot!")
    context.job_queue.run_repeating(scheduled_task, interval=15, first=5,
                                     chat_id=update.message.chat_id,
                                     data = {"user_id": user_id},
                                     name=str(user_id))


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    clear(user_id, context)

    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM german_items WHERE user_id = ?", (user_id, ))
    rows = cursor.fetchall()
    conn.commit()
    conn.close()
    
    if len(rows) < 5:
        await update.message.reply_text(f"📖❌ Not enough words in your dictionary 📚, please add more translated items! 😅🙌📈")
    else:
        context.application.user_data[user_id]['chatting'] = True 
        context.application.user_data[user_id]['wating_user'] = True
        await update.message.reply_text("Lets start guessing words! 🤓📚🔍✨")
        await asyncio.sleep(1)
        z = sample_word(user_id, db_filename=db_filename)
        context.application.user_data[user_id]['answer_guessing'] = z[0]
        await update.message.reply_text(z[0])
        
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("This is a help message")

def clear(user_id: str, context: ContextTypes.DEFAULT_TYPE):

    for flags in ['chatting', 'wating_user', 'add_items', 'answer_guessing']:
        if flags in context.user_data:
            del context.application.user_data[user_id][flags]

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    clear(user_id, context)

    await update.message.reply_text(f"That's it for now! {''.join(random.sample(list('💁👌📙👋'),random.randint(1, 3)))}", parse_mode="markdown")


async def add_items_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    clear(user_id, context)
    
    context.application.user_data[user_id]['add_items'] = True
    await update.message.reply_text(f"Please enter the pairs:\n\n*word - translation*\n\nEach pair should be in a new line 📝 or in a different message ✉️.", 
                                    parse_mode="markdown")
    
async def set_scheduled_wort_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id

    #delete previous job
    try:
        time = int(context.args[0])
    except:
        await update.message.reply_text("Please enter a valid time in seconds.")
        return
    
    time = int(context.args[0])

    job_name = str(update.effective_user.id)
    current_jobs = context.job_queue.get_jobs_by_name(job_name)

    if not current_jobs:
        await update.message.reply_text("No active scheduled task to modify.")
        return

    # Remove the existing job(s)
    for job in current_jobs:
        job.schedule_removal()
    
    if time > 0:
        context.job_queue.run_repeating(scheduled_task, interval=time, first=5,
                                            chat_id=update.message.chat_id,
                                            data = {"user_id": user_id},
                                            name=job_name)
        await update.message.reply_text(f"Timer set to {time} seconds 🕒🔔📚✨")
    else:
        await update.message.reply_text("Automatic requests disabled! 🛑🔕📚✨")


async def remove_item_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    clear(user_id, context)
    
    context.application.user_data[user_id]['remove_items'] = True
    await update.message.reply_text(f"📝 Please enter the word you want to remove from your dictionary. ❌📖.", 
                                    parse_mode="markdown")       
    
def add_items(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    list_items = text.split("\n")

    error =  None
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    
    for j, item in enumerate(list_items):

        if len(item.split("-")) != 2:
            error = j
            break

        word, translation = item.split("-")

        #check if the word for this useer is already in the database
        cursor.execute("SELECT id FROM german_items WHERE word = ? AND user_id = ?", (word.strip(), user_id))
        row = cursor.fetchall()

        if row is None:
            # Word does not exist, insert it
            word_id = uuid.uuid4()
            cursor.execute("INSERT INTO german_items (id, word, user_id, times_guessed) VALUES (?, ?, ?, ?)", (word_id, word.strip(), user_id, 0))
        else:
            assert len(row) == 1
            word_id = row[0][0]
        cui = uuid.uuid4()
        cursor.execute("INSERT INTO translations (id, source_word_id, translation) VALUES (?, ?, ?)", (cui, word_id, translation.strip()))
        
        conn.commit()
        print(f"Pair {word} -> {translation} added to vocabulary.")

    conn.commit()
    conn.close()

    success = '\n'.join([' > '.join(i.split('-')) for i in list_items[:error]])

    if error is not None:
       if not len(success):
              return f"Invalid format. Please enter the pairs in the format: \n *word - translation*"
       return [f"Invalid format in enty {error + 1}!\n\n {list_items[error]}\n\nPlease enter the pairs in the format: *word - translation*\n\n*You only have to re-enter the pairs from that line on.*",
          "*Successfully added pairs*:\n" + success]
    context.application.user_data[user_id]['add_items'] = False
    return ["Done! ✅😎", "*Successfully added pairs*:\n" + success]

def remove_item(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM german_items WHERE word = ? AND user_id = ?", (text.strip(), user_id))
    row = cursor.fetchall()

    if row is None:
        return f"Word '{text}' not found in your dictionary."
    else:
        assert len(row) == 1
        word_id = row[0][0]

    cursor.execute("DELETE FROM german_items WHERE id = ?", (word_id,))
    cursor.execute("DELETE FROM translations WHERE source_word_id = ?", (word_id,))

    conn.commit()
    conn.close()

    return f"Word '{text}' removed from your dictionary."


def handle_response(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:

    processed: str = text.strip()
    user_id = update.effective_user.id
    print(context.application.user_data[user_id])

    if context.application.user_data[user_id].get("wating_user", False):
        
        if check_response(processed, context.application.user_data[user_id]['answer_guessing']):
            z = sample_word(user_id, db_filename=db_filename) if context.application.user_data[user_id].get("chatting", False) else None
            nextt = []
            if z is not None:
                context.application.user_data[user_id]['answer_guessing'] = z[-1]
                nextt = [z[0]]
            else : 
                del context.application.user_data[user_id]['wating_user']
                del context.application.user_data[user_id]['answer_guessing']

            return [f"Correct!! {''.join(random.sample(list('🥳🎉🎊🤩💅😌💪'),random.randint(2, 4)))}"] + nextt
        else:
            return "❌ Incorrect! Try again 🔄😊"
    elif context.application.user_data[user_id].get("add_items", False):
        return add_items(processed, update, context)
    elif context.application.user_data[user_id].get("remove_items", False):
        return remove_item(processed, update, context)
    

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(f"User ({update.message.chat.id}) in ({message_type}): {text}")

    if message_type == "private":
        response: str = handle_response(text, update, context)
    elif message_type == "group":
        if text.startswith(BOT_USERNAME):
            response: str = handle_response(text.replace(BOT_USERNAME, ""), update, context)

    print("Bot: ", response)
    if isinstance(response, str):
        await update.message.reply_text(response)
    if isinstance(response, list):
        for r in response:
            await update.message.reply_text(r, parse_mode="markdown")
            await asyncio.sleep(0.5)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Update {update} caused error {context.error}")


def initialize_database():

    if not os.path.exists(db_filename):
        print(f"Database '{db_filename}' does not exist, creating a new one.")
    else:
        print(f"Database '{db_filename}' already exists.")

    conn = sqlite3.connect(db_filename)

    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tlgm_uid TEXT NOT NULL,
            username TEXT NOT NULL,
            timer INTEGER NOT NULL DEFAULT -1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS translations (
            id TEXT PRIMARY KEY,
            source_word_id INTEGER NOT NULL,
            translation TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS german_items (
            id TEXT PRIMARY KEY,
            word TEXT NOT NULL,
            user_id TEXT NOT NULL,
            times_guessed INTEGER NOT NULL DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()
    return conn, cursor


if __name__ == "__main__":

    print("Initializing Database...")
    initialize_database()

    print("Bot Starting...")
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("chat", chat_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("add_items", add_items_command))
    app.add_handler(CommandHandler("set_timer", set_scheduled_wort_timer))
    app.add_handler(CommandHandler("remove_item", remove_item_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, message_handler))
    
    # Error
    app.add_error_handler(error)

    print("Bot Started!")
    app.run_polling(poll_interval=1)
