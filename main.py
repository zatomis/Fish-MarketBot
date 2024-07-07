from urllib.error import URLError
from io import BytesIO
import requests
from environs import Env
import redis
from functools import partial
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Filters, Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


_database = None
strapi_token = ''


def get_products(token, product_id='', getimage=False):
    headers = {'Authorization': f'Bearer {token}'}
    url = 'http://localhost:1337/api/Products/'+product_id
    params = {}
    if getimage:
        params = {'populate': 'Picture'}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def main_menu():
    global strapi_token
    products = get_products(strapi_token)
    buttons = []
    for product in products['data']:
        buttons.append(
            [InlineKeyboardButton(text=product['attributes']['Title'], callback_data=product['id'])]
        )
    return InlineKeyboardMarkup(buttons)


def start(update: Update, context: CallbackContext):
    """
    Хэндлер для состояния START.
    Бот отвечает пользователю фразой "Привет!" и переводит его другое в состояние.
    Теперь в ответ на его команды будет запускаеться другой хэндлер.
    """
    update.message.reply_text('Список товаров!', reply_markup=main_menu())
    logger.info(update.message.message_id)
    return "HANDLE_MENU"


def back_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
    query.bot.send_message(update.callback_query.from_user.id, 'Список товаров!', reply_markup=main_menu())
    return "HANDLE_MENU"


def product_button(update: Update, context: CallbackContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()
    # query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message)
    try:
        global strapi_token
        product_title = get_products(strapi_token, query.data, getimage=True)
        picture_url = 'http://localhost:1337' + product_title['data']['attributes']['Picture']['data'][0]['attributes'][
            'url']
        description = product_title['data']['attributes']['Description']
        response = requests.get(picture_url)
        image_data = BytesIO(response.content)
        button_back = InlineKeyboardButton('Назад', callback_data='0')
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [button_back, ]
            ])
        query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
        query.bot.send_photo(update.callback_query.from_user.id, image_data,
                             caption=f"Описание товара:\n{description}", reply_markup=keyboard)
        return "HANDLE_DESCRIPTION"
    except URLError:
        update.callback_query.message.reply_text('Нет фото')
        return "START"
    except IndexError:
        update.callback_query.message.reply_text('Нет фото')
        return "START"
    # except IndexError as error:
    #     update.callback_query.message.reply_text('Нет фото')
    #     return "START"


def echo(update, context):
    """
    Хэндлер для состояния ECHO.
    Бот отвечает пользователю тем же, что пользователь ему написал.
    Оставляет пользователя в состоянии ECHO.
    """
    users_reply = update.message.text
    update.message.reply_text(users_reply)
    return "ECHO"


def handle_users_reply(update, context, host, port):
    """
    Функция, которая запускается при любом сообщении от пользователя и решает как его обработать.
    Эта функция запускается в ответ на эти действия пользователя:
        * Нажатие на inline-кнопку в боте
        * Отправка сообщения боту
        * Отправка команды боту
    Она получает стейт пользователя из базы данных и запускает соответствующую функцию-обработчик (хэндлер).
    Функция-обработчик возвращает следующее состояние, которое записывается в базу данных.
    Если пользователь только начал пользоваться ботом, Telegram форсит его написать "/start",
    поэтому по этой фразе выставляется стартовое состояние.
    Если пользователь захочет начать общение с ботом заново, он также может воспользоваться этой командой.
    """
    global strapi_token
    db = get_database_connection(host, port)
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': product_button,
        'HANDLE_DESCRIPTION': back_button,
        'ECHO': echo
    }
    state_handler = states_functions[user_state]
    # Если вы вдруг не заметите, что python-telegram-bot перехватывает ошибки.
    # Оставляю этот try...except, чтобы код не падал молча.
    # Этот фрагмент можно переписать.
    try:
        next_state = state_handler(update, context)
        logger.info("next_state "+next_state)
        db.set(chat_id, next_state)
    except Exception as err:
        print(err)


def get_database_connection(database_host, database_port):
    """
    Возвращает конекшн с базой данных Redis, либо создаёт новый, если он ещё не создан.
    """
    global _database
    if _database is None:
        _database = redis.Redis(host=database_host, port=database_port, db=0, protocol=3)
    return _database


if __name__ == '__main__':
    env = Env()
    env.read_env()
    host = env('REDIS_HOST')
    port = env('REDIS_PORT')
    strapi_token = env.str("STRAPI_TOKEN")
    token = env.str("TELEGRAM_TOKEN")
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(partial(handle_users_reply, host=host, port=port)))
    dispatcher.add_handler(MessageHandler(Filters.text, partial(handle_users_reply, host=host, port=port)))
    dispatcher.add_handler(CommandHandler('start', partial(handle_users_reply, host=host, port=port)))
    updater.start_polling()
    updater.idle()
