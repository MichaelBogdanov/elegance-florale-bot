import threading
import html
from loader import bot
from telebot import types
from config import ADMINS, REVIEW_CHANNEL_ID
from utils import get_products_by_category, get_product_by_id
from states import user_products, user_index, user_photo_index

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ОТЗЫВОВ ---
is_writing_review = {}     
user_reviews_collector = {} 
ui_timers = {} 
data_lock = threading.Lock() 

# --- 1. ЛОВЕЦ СООБЩЕНИЙ И ОБНОВЛЕНИЕ ИНТЕРФЕЙСА ---

def update_review_ui(user_id, chat_id):
    """Плавное обновление счетчика (чтобы не словить блок от Telegram)"""
    with data_lock:
        data = user_reviews_collector.get(user_id)
        if not data: return
        
        t_len = sum(len(t) for t in data['text_parts'])
        p_count = len(data['photos'])
        v_count = len(data['videos'])
        d_count = len(data['docs'])
        msg_id = data['main_msg_id']

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Опубликовать отзыв", callback_data="publish_review"))
    
    updated_text = (
        "📥 <b>Файлы успешно добавлены в корзину!</b>\n\n"
        f"📝 <b>Текст:</b> {t_len} символов\n"
        f"📸 <b>Фотографий:</b> {p_count}\n"
        f"🎥 <b>Видео:</b> {v_count}\n"
    )
    if d_count > 0:
        updated_text += f"📄 <b>Документов:</b> {d_count}\n"
        
    updated_text += (
        "\n<i>Убедитесь, что счетчик выше совпадает с тем, что вы отправили.\n"
        "Как только загрузка завершится — жмите кнопку ниже! 👇</i>"
    )

    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=updated_text,
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception:
        pass # Игнорируем, если текст не изменился


# ВАЖНО: Мы убрали тут @bot.message_handler, чтобы зарегистрировать его особым способом ниже!
def handle_review_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    with data_lock:
        data = user_reviews_collector.get(user_id)
        if not data:
            return

        # 1. Собираем текст
        text_to_save = message.text or message.caption
        if text_to_save:
            data['text_parts'].append(text_to_save)

        # 2. Собираем медиа
        if message.content_type == 'photo':
            data['photos'].append(message.photo[-1].file_id)
        elif message.content_type == 'video':
            data['videos'].append(message.video.file_id)
        elif message.content_type == 'document':
            data['docs'].append(message.document.file_id)

    # Обновляем интерфейс с задержкой в 1.5 секунды
    if user_id in ui_timers:
        ui_timers[user_id].cancel()
    ui_timers[user_id] = threading.Timer(1.5, update_review_ui, args=[user_id, chat_id])
    ui_timers[user_id].start()


# =====================================================================
# 🔥 ХАК ДЛЯ ПЕРЕХВАТА ФОТОГРАФИЙ (ОБХОД АДМИНКИ)
# =====================================================================
bot.register_message_handler(
    handle_review_messages, 
    func=lambda msg: is_writing_review.get(msg.from_user.id, False), # Срабатывает ТОЛЬКО во время отзыва
    content_types=['text', 'photo', 'video', 'document']
)
# Перемещаем наш обработчик в САМОЕ НАЧАЛО очереди. 
# Теперь он будет забирать фото первым, и ваша админка не сможет их украсть!
if bot.message_handlers:
    bot.message_handlers.insert(0, bot.message_handlers.pop())
# =====================================================================


# --- 2. CALLBACK ROUTER (КАТАЛОГ, ЗАКАЗЫ, КНОПКИ) ---

@bot.callback_query_handler(func=lambda call: True)
def callback_router(callback):
    data = callback.data
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # ==========================================
    # КНОПКА: ПУБЛИКАЦИЯ ОТЗЫВА
    # ==========================================
    if data == "publish_review":
        bot.answer_callback_query(callback.id)
        
        with data_lock:
            if not is_writing_review.get(user_id):
                return
            data_coll = user_reviews_collector.pop(user_id, {})
            is_writing_review[user_id] = False
            
        if user_id in ui_timers:
            ui_timers[user_id].cancel()
        
        try: bot.delete_message(chat_id, callback.message.message_id)
        except: pass

        if not data_coll or (not data_coll['photos'] and not data_coll['videos'] and not data_coll['text_parts'] and not data_coll['docs']):
            bot.send_message(chat_id, "Вы не прислали текст или медиа 🤷‍♂️ Отзыв отменен.")
            return

        raw_text = "\n\n".join(data_coll['text_parts']) if data_coll['text_parts'] else "Без текста"
        if len(raw_text) > 800: raw_text = raw_text[:800] + "...\n(текст обрезан)"
        safe_text = html.escape(raw_text)
        
        user_link = f'<a href="tg://openmessage?user_id={user_id}">{html.escape(callback.from_user.first_name)}</a>'
        username_text = f"@{callback.from_user.username}" if callback.from_user.username else "скрыт"
        caption = f"📖 <b>Новый отзыв!</b>\n\n👤 <b>От:</b> {user_link} ({username_text})\n\n<b>Текст:</b>\n{safe_text}"

        try:
            media_to_send = []
            for pid in data_coll['photos']:
                media_to_send.append(types.InputMediaPhoto(pid))
            for vid in data_coll['videos']:
                media_to_send.append(types.InputMediaVideo(vid))

            if not media_to_send:
                bot.send_message(REVIEW_CHANNEL_ID, caption, parse_mode="HTML")
            elif len(media_to_send) == 1:
                item = media_to_send[0]
                if isinstance(item, types.InputMediaPhoto):
                    bot.send_photo(REVIEW_CHANNEL_ID, item.media, caption=caption, parse_mode="HTML")
                else:
                    bot.send_video(REVIEW_CHANNEL_ID, item.media, caption=caption, parse_mode="HTML")
            else:
                media_to_send = media_to_send[:10]
                media_to_send[0].caption = caption
                media_to_send[0].parse_mode = "HTML"
                bot.send_media_group(REVIEW_CHANNEL_ID, media_to_send)
                
            for doc_id in data_coll['docs']:
                bot.send_document(REVIEW_CHANNEL_ID, doc_id, caption="📄 Прикрепленный документ")

            bot.send_message(chat_id, "✅ Ваш отзыв успешно опубликован! Большое спасибо! ❤️")
            
        except Exception as e:
            print(f"Ошибка публикации отзыва: {e}")
            bot.send_message(chat_id, "❌ Произошла ошибка при отправке отзыва в канал.")

    # ==========================================
    # КАТАЛОГ И ЗАКАЗЫ
    # ==========================================

    elif data == "catalog":
        is_writing_review[user_id] = False
        bot.answer_callback_query(callback.id)
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("💐 Букеты", callback_data="category_bouquet")
        btn2 = types.InlineKeyboardButton("🌸 Одиночные", callback_data="category_single")
        btn3 = types.InlineKeyboardButton("🎨 Авторские изделия", callback_data="category_handmade")
        markup.row(btn1, btn2)
        markup.row(btn3)
        
        menu_text = "Выберите категорию товаров:"
        try: bot.edit_message_text(menu_text, chat_id, callback.message.message_id, reply_markup=markup)
        except:
            bot.delete_message(chat_id, callback.message.message_id)
            bot.send_message(chat_id, menu_text, reply_markup=markup)

    elif data.startswith("category_"):
        bot.answer_callback_query(callback.id)
        category = data.split("_")[1]
        products = get_products_by_category(category)
        if not products:
            bot.answer_callback_query(callback.id, "В этой категории пока пусто 😢", show_alert=True)
            return
        user_products[user_id] = products
        user_index[user_id] = 0
        user_photo_index[user_id] = 0
        show_product(user_id, chat_id, callback.message.message_id, products[0], len(products), 0)

    elif data == "go_next":
        bot.answer_callback_query(callback.id)
        products = user_products.get(user_id)
        if not products: return
        idx = (user_index.get(user_id, 0) + 1) % len(products)
        user_index[user_id] = idx
        user_photo_index[user_id] = 0
        show_product(user_id, chat_id, callback.message.message_id, products[idx], len(products), 0)

    elif data == "go_next_photo":
        bot.answer_callback_query(callback.id)
        products = user_products.get(user_id)
        if not products: return
        product = products[user_index.get(user_id, 0)]
        idx = (user_photo_index.get(user_id, 0) + 1) % len(product.get("photos", []))
        user_photo_index[user_id] = idx
        show_product(user_id, chat_id, callback.message.message_id, product, len(products), idx)

    elif data.startswith("zakaz_"):

        bot.answer_callback_query(callback.id)
        p_id = int(data.split("_")[1])
        product = get_product_by_id(p_id)
        if not product: return
        
        confirm_text = (
            f"❓ <b>Подтверждение заявки</b>\n\n"
            f"Вы собираетесь отправить заявку на товар:\n"
            f"💐 <b>{product['name']}</b>\n\n"
            f"Пожалуйста, подтвердите ваше действие."
        )

        
        markup = types.InlineKeyboardMarkup()
        yes_btn = types.InlineKeyboardButton("✅ Да, подтверждаю", callback_data=f"confirm_order_{p_id}")
        no_btn = types.InlineKeyboardButton("❌ Вернуться назад", callback_data="catalog")
        markup.row(yes_btn, no_btn)
        
        bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=confirm_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
        
    elif data.startswith("confirm_order_"):
        
        bot.answer_callback_query(callback.id)
        p_id = int(data.split("_")[1])
        product = get_product_by_id(p_id)
        if not product: return
        
        user = callback.from_user
        name = user.first_name if user.first_name else "Клиент"
        user_link = f'<a href="tg://openmessage?user_id={user.id}">{html.escape(name)}</a>'
        username_text = f"@{user.username}" if user.username else "скрыт"
        
        admin_text = (
            f"🛍 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
            f"👤 <b>Клиент:</b> {user_link}\n"
            f"📱 <b>Связь:</b> {username_text}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"💐 <b>Товар:</b> {product['name']} (№{product['id']})"
        )
        
        markup = types.InlineKeyboardMarkup()
        contact_btn = types.InlineKeyboardButton("💬 Написать клиенту", url=f"tg://user?id={user.id}")
        adminbtn = types.InlineKeyboardButton("✅ Заказ выполнен", callback_data=f"confirm_{user.id}")
        
        bot.send_message(chat_id, f"✅ Заявка на «{product['name']}» отправлена!\n\nВ ближайшее время специалист свяжется с вами для уточнения деталей. Благодарим за обращение! ✨")
        
        try:
            markup.add(contact_btn)
            markup.add(adminbtn)
            bot.send_message(-1003868129054, admin_text, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            if "BUTTON_USER_PRIVACY_RESTRICTED" in str(e):
                bot.send_message(chat_id, f"Ой, кажется, ваш профиль скрыт настройками приватности. Измените их и попробуйте ещё раз! ✨")

    elif data.startswith("confirm_"):
        c_id = int(data.split("_")[1])
        bot.answer_callback_query(callback.id, "Уведомление отправлено!")
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Оставить отзыв📖", callback_data="review"))
        
        try:
            bot.send_message(c_id, "🎉 <b>Ваш заказ выполнен!</b>\n\nСпасибо, что выбрали Elégance Florale. Будем рады видеть вас снова! 🌸", parse_mode="HTML", reply_markup=markup)
            bot.edit_message_text(
                chat_id=chat_id, message_id=callback.message.message_id,
                text=callback.message.text + f"\n\n✅ <b>Выполнено: {callback.from_user.first_name}</b>",
                parse_mode="HTML", reply_markup=None
            )
        except Exception:
            pass

    # КНОПКА СТАРТА ОТЗЫВА
    elif data == "review":
        bot.answer_callback_query(callback.id)
        
        with data_lock:
            is_writing_review[user_id] = True
            user_reviews_collector[user_id] = {
                'photos': [], 'videos': [], 'docs': [], 'text_parts': [], 
                'main_msg_id': callback.message.message_id
            }
        
        instruction_text = (
            "✍️ <b>Напишите свой отзыв!</b>\n\n"
            "Вы можете отправить текст, фото или видео.\n"
            "Я соберу их вместе в один красивый пост!\n\n"
            "<b>Отправляйте файлы, и как только счетчик загрузки обновится, нажмите кнопку ниже 👇</b>"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Завершить и опубликовать", callback_data="publish_review"))
        
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=callback.message.message_id, text=instruction_text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, instruction_text, parse_mode="HTML", reply_markup=markup)


# --- 3. ФУНКЦИЯ ОТРИСОВКИ ТОВАРА ---

def show_product(userrr, chat_id, message_id, product, total_count, photo_index=0):
    clean_name = html.escape(product['name'])
    clean_desc = html.escape(product['description'])
    clean_id = html.escape(str(product['id']))
    
    if userrr not in ADMINS:
        caption = f"💐 <b>{clean_name}</b>\n\n{clean_desc}\n\n💰 Цена: <b>{product['price']} руб.</b>"
    else:
        caption = f" Товар №{clean_id}\n\n💐 <b>{clean_name}</b>\n\n{clean_desc}\n\n💰 Цена: <b>{product['price']} руб.</b>"
    
    photos = product.get("photos", [])
    current_photo = photos[photo_index] if photos else product.get("photo")

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("Заказать 💌", callback_data=f"zakaz_{product['id']}"))
    if len(photos) > 1:
        markup.row(types.InlineKeyboardButton(f"Фото {photo_index+1}/{len(photos)} 📷", callback_data="go_next_photo"))
    if total_count > 1:
        markup.row(types.InlineKeyboardButton("Далее ➡️", callback_data="go_next"))
    markup.row(types.InlineKeyboardButton("Назад в меню ↩️", callback_data="catalog"))

    if not current_photo:
        bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=markup)
        return

    try:
        bot.edit_message_media(media=types.InputMediaPhoto(current_photo, caption=caption, parse_mode="HTML"), chat_id=chat_id, message_id=message_id, reply_markup=markup)
    except Exception:
        try: bot.delete_message(chat_id, message_id)
        except: pass
        bot.send_photo(chat_id, current_photo, caption=caption, parse_mode="HTML", reply_markup=markup)



