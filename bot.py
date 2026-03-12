
import threading
import time
from datetime import datetime, timedelta
from loader import bot
from utils import init_db, get_connection

# Импортируем хендлеры, чтобы они зарегистрировались
import handlers.start
import handlers.admin
import handlers.callback

def reminder_scheduler():
    while True:
        try:
            # Считаем, какой день будет через 15 дней
            target_date = datetime.now() + timedelta(days=15)
            day = target_date.day
            month = target_date.month
            
            conn = get_connection()
            cur = conn.cursor()
            # Ищем всех, у кого совпадает день и месяц
            cur.execute("SELECT user_id, description FROM reminders WHERE date_day=%s AND date_month=%s", (day, month))
            reminders = cur.fetchall()
            
            for r in reminders:
                user_id, desc = r
                text = f"🌸 <b>Напоминание!</b>\n\nЧерез 15 дней праздник: <b>{desc}</b>. Пора задуматься о подарке! Чтобы заказать заранее, загляните в /catalog"
                try:
                    bot.send_message(user_id, text, parse_mode="HTML")
                except:
                    pass # Если пользователь заблокировал бота
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Ошибка в планировщике: {e}")
            
        # Ждем 24 часа до следующей проверки (86400 секунд)
        time.sleep(86400)

if __name__ == "__main__":
    threading.Thread(target=reminder_scheduler, daemon=True).start()
    print("Инициализация базы данных...")
    init_db()
    
    print("Бот запущен...")
    # remove_webhook нужен, если бот до этого работал на вебхуках, чтобы не было конфликта
    bot.delete_webhook(drop_pending_updates=True) 
    bot.polling(non_stop=True)
