from dotenv import load_dotenv
load_dotenv()

import telebot
from config import TOKEN

bot = telebot.TeleBot(TOKEN)