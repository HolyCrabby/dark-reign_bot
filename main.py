import logging
import sqlite3
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# ТОКЕН БОТА - отримуємо з змінних середовища або вставляємо напряму
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7843448143:AAGOT2t0KgoB-fbFOfJamyvh-IvjY7BsBR8')

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# База даних
DATABASE_PATH = 'dark_reign.db'

def init_database():
    """Ініціалізація бази даних"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            language TEXT DEFAULT 'uk',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS towers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            level INTEGER DEFAULT 1,
            gold INTEGER DEFAULT 205,
            wood INTEGER DEFAULT 50,
            stone INTEGER DEFAULT 50,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS minions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            health INTEGER DEFAULT 100,
            attack INTEGER DEFAULT 10,
            defense INTEGER DEFAULT 5,
            is_on_mission BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def create_user(telegram_id, username=None, language='uk'):
    """Створення нового користувача"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO users (telegram_id, username, language) VALUES (?, ?, ?)', 
                      (telegram_id, username, language))
        user_id = cursor.lastrowid
        
        cursor.execute('INSERT INTO towers (user_id, gold, wood, stone) VALUES (?, ?, ?, ?)', 
                      (user_id, 205, 50, 50))
        
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def user_exists(telegram_id):
    """Перевірка існування користувача"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_user_data(telegram_id):
    """Отримання даних користувача"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, u.language, t.level, t.gold, t.wood, t.stone
        FROM users u
        JOIN towers t ON u.id = t.user_id  
        WHERE u.telegram_id = ?
    ''', (telegram_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'user_id': result[0], 'language': result[1], 'tower_level': result[2],
            'gold': result[3], 'wood': result[4], 'stone': result[5]
        }
    return None

def set_user_language(telegram_id, language):
    """Встановлення мови користувача"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET language = ? WHERE telegram_id = ?', (language, telegram_id))
    conn.commit()
    conn.close()

def hire_minion(telegram_id, name):
    """Найняти посіпаку"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
    user_id = cursor.fetchone()[0]
    
    cursor.execute('INSERT INTO minions (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()
    conn.close()

def get_user_minions(telegram_id):
    """Отримання посіпак користувача"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.name, m.level, m.health, m.attack, m.defense
        FROM minions m
        JOIN users u ON m.user_id = u.id
        WHERE u.telegram_id = ?
    ''', (telegram_id,))
    
    results = cursor.fetchall()
    conn.close()
    return [{'name': r[0], 'level': r[1], 'health': r[2], 'attack': r[3], 'defense': r[4]} for r in results]

# Кнопки знизу (головне меню)
def main_reply_keyboard(language='en'):
    if language == 'uk':
        keyboard = [
            [KeyboardButton("🏰 Башта"), KeyboardButton("⚔️ Посіпаки")],
            [KeyboardButton("📜 Місії"), KeyboardButton("🏗️ Будівлі")],
            [KeyboardButton("❓ Допомога"), KeyboardButton("🌐 Мова")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🏰 Tower"), KeyboardButton("⚔️ Minions")],
            [KeyboardButton("📜 Missions"), KeyboardButton("🏗️ Buildings")], 
            [KeyboardButton("❓ Help"), KeyboardButton("🌐 Language")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def language_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ])

# Тексти
TEXTS = {
    'uk': {
        'welcome_new': "🏰 Ласкаво просимо до Dark Reign!\n\nВиберіть мову:",
        'welcome_back': "🏰 З поверненням, Темний Лорде!",
        'tower_info': "🏰 Ваша Башта (Рівень {tower_level})\n💰 Золото: {gold}\n🪵 Дерево: {wood}\n🗿 Камінь: {stone}",
        'no_minions': "⚔️ У вас поки немає посіпак.",
        'minion_hired': "⚔️ Ви найняли: {name}!",
        'language_changed': "🇺🇦 Мову змінено на українську"
    },
    'en': {
        'welcome_new': "🏰 Welcome to Dark Reign!\n\nChoose your language:",
        'welcome_back': "🏰 Welcome back, Dark Lord!",
        'tower_info': "🏰 Your Tower (Level {tower_level})\n💰 Gold: {gold}\n🪵 Wood: {wood}\n🗿 Stone: {stone}",
        'no_minions': "⚔️ You have no minions yet.",
        'minion_hired': "⚔️ You hired: {name}!",
        'language_changed': "🇺🇸 Language changed to English"
    }
}

def get_text(language, key, **kwargs):
    text = TEXTS.get(language, TEXTS['uk']).get(key, key)
    return text.format(**kwargs) if kwargs else text

# Обробники команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    if not user_exists(telegram_id):
        text = get_text('uk', 'welcome_new')
        await update.message.reply_text(text, reply_markup=language_keyboard())
        return
    
    user_data = get_user_data(telegram_id)
    language = user_data['language']
    
    welcome_text = get_text(language, 'welcome_back')
    tower_text = get_text(language, 'tower_info', **user_data)
    
    await update.message.reply_text(f"{welcome_text}\n\n{tower_text}", 
                                  reply_markup=main_reply_keyboard(language))

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок знизу"""
    text = update.message.text
    telegram_id = update.effective_user.id
    
    if not user_exists(telegram_id):
        await start_command(update, context)
        return
    
    user_data = get_user_data(telegram_id)
    language = user_data['language']
    
    if text in ["🏰 Башта", "🏰 Tower"]:
        tower_text = get_text(language, 'tower_info', **user_data)
        await update.message.reply_text(tower_text)
        
    elif text in ["⚔️ Посіпаки", "⚔️ Minions"]:
        minions = get_user_minions(telegram_id)
        if not minions:
            text_msg = get_text(language, 'no_minions')
        else:
            text_msg = f"⚔️ {'Ваші Посіпаки' if language == 'uk' else 'Your Minions'}:\n"
            for minion in minions:
                text_msg += f"• {minion['name']} (Level {minion['level']})\n"
        
        # Додаємо кнопку найму
        keyboard = [[InlineKeyboardButton(
            "📝 Найняти посіпаку" if language == 'uk' else "📝 Hire Minion", 
            callback_data="hire_minion"
        )]]
        await update.message.reply_text(text_msg, reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif text in ["📜 Місії", "📜 Missions"]:
        missions_text = "📜 Місії поки що розробляються..." if language == 'uk' else "📜 Missions are under development..."
        await update.message.reply_text(missions_text)
        
    elif text in ["🏗️ Будівлі", "🏗️ Buildings"]:
        buildings_text = "🏗️ Будівлі поки що розробляються..." if language == 'uk' else "🏗️ Buildings are under development..."
        await update.message.reply_text(buildings_text)
        
    elif text in ["❓ Допомога", "❓ Help"]:
        help_text = ("🏰 Dark Reign - гра про темного лорда!\n\n"
                    "🏰 Башта - ваша головна база\n"
                    "⚔️ Посіпаки - ваші воїни\n"
                    "📜 Місії - завдання для посіпак\n"
                    "🏗️ Будівлі - покращення башти") if language == 'uk' else \
                   ("🏰 Dark Reign - a dark lord game!\n\n"
                    "🏰 Tower - your main base\n"
                    "⚔️ Minions - your warriors\n"
                    "📜 Missions - tasks for minions\n"
                    "🏗️ Buildings - tower upgrades")
        await update.message.reply_text(help_text)
        
    elif text in ["🌐 Мова", "🌐 Language"]:
        lang_text = "🌐 Choose your language / Виберіть мову:"
        await update.message.reply_text(lang_text, reply_markup=language_keyboard())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник callback кнопок"""
    query = update.callback_query
    telegram_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if data.startswith("lang_"):
        language = data.split("_")[1]
        
        if not user_exists(telegram_id):
            create_user(telegram_id, query.from_user.username, language)
        else:
            set_user_language(telegram_id, language)
        
        success_text = get_text(language, 'language_changed')
        
        # Показуємо головне меню після вибору мови
        user_data = get_user_data(telegram_id)
        welcome_text = get_text(language, 'welcome_back')
        tower_text = get_text(language, 'tower_info', **user_data)
        
        # Редагуємо повідомлення
        await query.edit_message_text(f"{success_text}\n\n{welcome_text}\n\n{tower_text}")
        
        # Показуємо кнопки через нове повідомлення
        await context.bot.send_message(
            chat_id=telegram_id,
            text="🎮 Використовуйте кнопки нижче:" if language == 'uk' else "🎮 Use the buttons below:",
            reply_markup=main_reply_keyboard(language)
        )
    
    elif data == "hire_minion":
        user_data = get_user_data(telegram_id)
        language = user_data['language']
        
        names = ['Grok', 'Zarg', 'Vex', 'Nix', 'Bane', 'Scar', 'Grim', 'Hex']
        name = random.choice(names)
        hire_minion(telegram_id, name)
        
        text = get_text(language, 'minion_hired', name=name)
        await query.edit_message_text(text)

def main():
    init_database()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    print("🏰 Dark Reign bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
