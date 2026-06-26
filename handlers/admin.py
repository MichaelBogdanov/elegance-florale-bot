from loader import bot
from telebot import types
from config import ADMINS, user_black_list
from utils import add_product, delete_product, get_connection, update_product_field

MAX_PRODUCT_PHOTOS = 10
from states import admin_state, new_product

@bot.message_handler(commands=['blacklist'])
def blacklist(message):
    if message.from_user.id not in ADMINS:
        return
    bot.send_message(message.chat.id, "Введите ID пользователя, которого хотите добавить в черный список:")
    admin_state[message.from_user.id] = {"step": "blasklist"}
@bot.message_handler(commands=['edit'])
def edit(message):
    if message.from_user.id not in ADMINS:
        return
    bot.send_message(message.chat.id, "Введите ID товара для редактирования:")
    admin_state[message.from_user.id] = {"step": "edit_id"}

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_"))
def edit_choose(callback):
    if callback.from_user.id not in ADMINS:
        return

    user_id = callback.from_user.id
    state = admin_state.get(user_id)

    if not state or state.get("step") != "edit_choose":
        return

    field = callback.data.replace("edit_", "")
    admin_state[user_id]["edit_field"] = field

    bot.answer_callback_query(callback.id)

    if field == "photo":
        admin_state[user_id]["step"] = "edit_photo"
        bot.send_message(callback.message.chat.id, "Отправьте новое фото:")
    else:
        admin_state[user_id]["step"] = "edit_value"
        bot.send_message(callback.message.chat.id, "Введите новое значение:")


    
@bot.message_handler(commands=['reset_db'])
def reset_db_command(message):
    if message.from_user.id not in ADMINS:
        return
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Очищаем таблицу (удаляет ВСЕ товары)
    cur.execute("DELETE FROM products;")
    
    # 2. Сбрасываем счетчик ID на единицу
    cur.execute("ALTER SEQUENCE products_id_seq RESTART WITH 1;")
    
    conn.commit()
    cur.close()
    conn.close()
    
    bot.send_message(message.chat.id, "База очищена, счетчик ID сброшен на 1! ✨")


# 🗑 Удаление
@bot.message_handler(commands=['delete'])
def delete_start(message):
    if message.from_user.id not in ADMINS:
        return
    bot.send_message(message.chat.id, "Введите ID товара для удаления:")
    admin_state[message.from_user.id] = {"step": "delete_id"}

# ➕ Добавление товара
@bot.message_handler(commands=['add'])
def add_start(message):
    if message.from_user.id not in ADMINS:
        return

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("💐 Букеты", callback_data="add_bouquet"),
        types.InlineKeyboardButton("🌸 Одиночные", callback_data="add_single")
    )
    markup.row(types.InlineKeyboardButton("🎨 Авторские изделия", callback_data="add_handmade"))
    bot.send_message(message.chat.id, "Выберите категорию для добавления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("add_"))
def choose_category(callback):
    if callback.from_user.id not in ADMINS:
        return
    bot.answer_callback_query(callback.id)

    category = callback.data.replace("add_", "")
    # В базе храним названия категорий как 'bouquet' или 'single'
    if category == "bouquet":
        cat_db = "bouquet"
    elif category == "single":
        cat_db = "single"
    else:
        cat_db = "handmade"

    user_id = callback.from_user.id
    new_product[user_id] = {"category": cat_db}
    admin_state[user_id] = {"step": "name"}

    bot.send_message(callback.message.chat.id, "Введите название товара:")

@bot.message_handler(content_types=['text'])
def admin_text_steps(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return

    state = admin_state.get(user_id)
    if not state:
        return

    step = state["step"]

    # --- Удаление ---
    if step == "delete_id":
        try:
            p_id = int(message.text)
            delete_product(p_id)
            bot.send_message(message.chat.id, f"Товар {p_id} удален ✅")
        except ValueError:
            bot.send_message(message.chat.id, "Ошибка. Введите число (ID).")
        
        admin_state.pop(user_id, None)
        return

    # --- Добавление ---
    if step == "name":
        new_product[user_id]["name"] = message.text
        admin_state[user_id]["step"] = "description"
        bot.send_message(message.chat.id, "Введите описание:")
        return

    if step == "description":
        new_product[user_id]["description"] = message.text
        admin_state[user_id]["step"] = "price"
        bot.send_message(message.chat.id, "Введите цену (только цифры):")
        return

    if step == "price":
        try:
            price = int(message.text)
            new_product[user_id]["price"] = price
            admin_state[user_id]["step"] = "photo"
            new_product[user_id]["photos"] = []
            bot.send_message(message.chat.id, "Отправьте фото товара (можно несколько). Когда закончите, отправьте /done")
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите цену числом.")
        return
    if step == "edit_id":
        try:
            p_id = int(message.text)
            admin_state[user_id] = {"step": "edit_choose", "product_id": p_id}
    
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("Название", callback_data="edit_name"),
                types.InlineKeyboardButton("Описание", callback_data="edit_description")
            )
            markup.row(
                types.InlineKeyboardButton("Цена", callback_data="edit_price"),
                types.InlineKeyboardButton("Фото", callback_data="edit_photo")
            )
    
            bot.send_message(message.chat.id, "Что изменить?", reply_markup=markup)
    
        except ValueError:
            bot.send_message(message.chat.id, "Введите корректный ID.")

        return
    if step == "photo" and message.text == "/done":
        photos = new_product[user_id].get("photos", [])
        if not photos:
            bot.send_message(message.chat.id, "Вы еще не добавили ни одной фотографии.")
            return

        product = new_product[user_id]

        add_product(
            product["name"],
            product["description"],
            product["price"],
            photos,
            product["category"]
        )

        bot.send_message(message.chat.id, f"Товар '{product['name']}' добавлен ✅ (фото: {len(photos)})")

        admin_state.pop(user_id, None)
        new_product.pop(user_id, None)
        return

    if step == "edit_value":
        product_id = state["product_id"]
        field = state["edit_field"]
    
        value = message.text
        if field == "price":
            try:
                value = int(value)
            except ValueError:
                bot.send_message(message.chat.id, "Цена должна быть числом.")
                return

        update_product_field(product_id, field, value)
    
        bot.send_message(message.chat.id, "Товар обновлён ✅")
        admin_state.pop(user_id, None)
        return
    
    if step == "blacklist":
        black_list_id = message.text
        user_black_list.append(black_list_id)
        bot.send_message(message.chat.id, "Пользователь добавлен в черный список ✅")
        admin_state.pop(user_id, None)
        return

@bot.message_handler(content_types=['photo'])
def admin_photo_step(message):
    user_id = message.from_user.id
    state = admin_state.get(user_id)

    if not state:
        return

    # --- ДОБАВЛЕНИЕ ТОВАРА ---
    if state["step"] == "photo":
        file_id = message.photo[-1].file_id
        product = new_product.setdefault(user_id, {})
        photos = product.setdefault("photos", [])

        if len(photos) >= MAX_PRODUCT_PHOTOS:
            bot.send_message(message.chat.id, f"Можно добавить максимум {MAX_PRODUCT_PHOTOS} фото. Отправьте /done")
            return

        photos.append(file_id)
        bot.send_message(message.chat.id, f"Фото добавлено ({len(photos)}). Добавьте ещё или отправьте /done")
        return

    # --- РЕДАКТИРОВАНИЕ ФОТО ---
    if state["step"] == "edit_photo":
        product_id = state["product_id"]
        file_id = message.photo[-1].file_id

        update_product_field(product_id, "photo", [file_id])

        bot.send_message(message.chat.id, "Фото обновлено ✅")
        admin_state.pop(user_id, None)
        return





