from loader import bot
from telebot import types

@bot.message_handler(commands=['start'])
def start(message):
    text = (
        "Добро пожаловать в мастерскую авторских цветов Elégance Florale🌸\n\n"
        "Здесь создаются ручные изделия, которые дарят эмоции и остаются в памяти.\n\n"
        "Вы можете выбрать готовое изделие или изделие под свой индивидуальный заказ.\n\n"
        "Давайте вместе наполнять жизнь красотой и уютом💐"
    )

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("Каталог", callback_data="catalog")
    markup.row(btn1)
    
    # Отправляем фото или просто текст, если логотипа нет
    # bot.send_photo(message.chat.id, "URL_ИЛИ_ID_ФОТО", caption=text, reply_markup=markup)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=['pashalka'])
def babuin(message):
    bot.send_message(message.chat.id, "Лучший тгк в мире: https://t.me/MANDREL_OFF")

@bot.message_handler(commands=['catalog'])
def catalog_command(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("💐 Букеты", callback_data="category_bouquet")
    btn2 = types.InlineKeyboardButton("🌸 Одиночные", callback_data="category_single")
    btn3 = types.InlineKeyboardButton("🎨 Авторские изделия", callback_data="category_handmade")
    markup.row(btn1, btn2)
    markup.row(btn3)
    bot.send_message(message.chat.id, "Выберите категорию товаров:", reply_markup=markup)

@bot.message_handler(commands=['mydate'])
def mydate_start(message):
    msg = bot.send_message(message.chat.id, "Введите дату и название праздника в формате:\n`ДД.ММ Название` (например: `15.05 День рождения мамы`)", parse_mode="Markdown")
    bot.register_next_step_handler(msg, save_date_step)

def save_date_step(message):
    if '/' in message.text:
        pass
    try:
        parts = message.text.split(" ", 1)
        date_parts = parts[0].split(".")
        day = int(date_parts[0])
        month = int(date_parts[1])
        desc = parts[1]
        
        from utils import add_reminder
        add_reminder(message.from_user.id, day, month, desc)
        
        bot.send_message(message.chat.id, f"✅ Сохранила! Я напомню вам о празднике «{desc}» за 10 дней.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка в формате. Попробуйте еще раз команду /mydate")












