from urllib.error import URLError
from io import BytesIO
import requests
from environs import Env
import redis
from functools import partial
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Filters, Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler
import json

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


_database = None
strapi_token = ''

def get_host_port(value_host_port=''):
    host = value_host_port.get(list(value_host_port)[0])
    port = list(value_host_port)[0]
    return host, port


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
    keyboard = [
        [InlineKeyboardButton("Список товаров", callback_data="product_list")],
        [InlineKeyboardButton("Моя корзина", callback_data="my_cart")],
        [InlineKeyboardButton("Очистить корзину", callback_data="clear_cart")],
    ]
    return InlineKeyboardMarkup(keyboard)



def products_menu():
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
    update.message.reply_text('Бот Магазин - "Рыба Моя"🐟', reply_markup=main_menu())
    logger.info(update.message.message_id)
    return "START_MENU"


# def cart_choise_button(update: Update, context: CallbackContext) -> None:


# token1 = "346d69f83df097818c5e9e31e6c572a3591867437fc1f1072ee5e4cff813b75f96d82acff793ce9cdd93b4d77e6ef94a30527864ade03094332bb1439fe051948c772beb3349a537e618c2472db44e1e8548a614292dc6699bf5926d51c612cba214a768cee3f0b0f51d8662e58dcf37c4bab1424ca388da5c97ee1dd5ec21e8"
# headers = {'Authorization': f'Bearer {token1}'}
# url = 'http://localhost:1337/api/carts/'
# params = {'populate': 'user_orders'}
# params = {
#         'populate': 'user_orders',
#         'filters[cart_id]][$eq]': '2222'
#          }
# response = requests.get(url, headers=headers, params=params)
# response.raise_for_status()
# a = response.json()
# # a['meta']['pagination']['total'] = 0


def product_choise_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    match query.data:
        case 'back':
            query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
            query.bot.send_message(update.callback_query.from_user.id, 'Список товаров!', reply_markup=products_menu())
            return "HANDLE_MENU"
        case 'main_menu':
            query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
            query.bot.send_message(update.callback_query.from_user.id, 'Главное меню', reply_markup=main_menu())
            return "START_MENU"
        case 'add_cart':
            query.bot.send_message(update.callback_query.from_user.id, 'Укажите вес товара в граммах')
            return "ECHO"


def process_orders(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if int(query.data) > 0:
        # удалить позицию из заказа
        global strapi_token
        headers = {'Authorization': f'Bearer {strapi_token}'}
        response = requests.delete(f'http://localhost:1337/api/user-orders/{query.data}')
        response.raise_for_status()
        query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
        query.bot.send_message(update.callback_query.from_user.id, f'Бот Магазин - "Рыба Моя"🐟', reply_markup=main_menu())
        return "START_MENU"
    else:
        match query.data:
            case '0':
                pass
            case '-1':
                pass

def main_menu_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    match query.data:
        case 'product_list':
            query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
            query.bot.send_message(update.callback_query.from_user.id, 'Список товаров!', reply_markup=products_menu())
            return "HANDLE_MENU"
        case 'my_cart':
            #показать позиции заказа пользователя c ценами, корзину итоговую формировать по кнопке К оформлению
            query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
            global strapi_token
            headers = {'Authorization': f'Bearer {strapi_token}'}
            params = {
                    'populate': 'product',
                    'filters[user_id]][$eq]': update.callback_query.from_user.id,
                     }
            response = requests.get('http://localhost:1337/api/user-orders/',
                                     headers=headers, params=params)
            response.raise_for_status()
            orders = response.json()['data']
            if orders:
                buttons = []
                order_price = 0
                for order in orders:
                    position_total = order['attributes']['quantity']*order['attributes']['product']['data']['attributes']['Price']
                    buttons.append(
                        [
                            InlineKeyboardButton(text=order['attributes']['product']['data']['attributes']['Title'], callback_data=str(order['id'])),
                            InlineKeyboardButton(text=f"{order['attributes']['quantity']}x{order['attributes']['product']['data']['attributes']['Price']}={position_total}"'❌', callback_data=str(order['id'])),
                         ]
                    )
                    order_price = order_price + position_total
                buttons.append([InlineKeyboardButton(text='Оформить заказ', callback_data='0')])
                buttons.append([InlineKeyboardButton(text='Главное меню', callback_data='-1')])
                reply_markup = InlineKeyboardMarkup(buttons)
                query.bot.send_message(update.callback_query.from_user.id, f'Итого по заказу {order_price}', reply_markup=reply_markup)
                return "HANDLE_USER_ORDER"
            else:
                query.bot.send_message(update.callback_query.from_user.id, f'Корзина пуста 🤷', reply_markup=main_menu())
            return "START_MENU"

        case 'clear_cart':
            # # global strapi_token
            # headers = {'Authorization': f'Bearer {strapi_token}'}
            # params = {'data': {'cart_id': f"{update.callback_query.from_user.id}", 'user_orders': [10, 11]}}
            # response = requests.post('http://localhost:1337/api/carts/',
            #                          headers=headers, json=params)
            # response.raise_for_status()
            # new_cart = json.loads(response.text)['data']['id']


            return "HANDLE_DESCRIPTION"


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
        keyboard = [
            [
                InlineKeyboardButton("Назад", callback_data="back"),
                InlineKeyboardButton("В корзину", callback_data="add_cart"),
            ],
            [InlineKeyboardButton("Главное меню", callback_data="main_menu")],
        ]

        query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
        query.bot.send_photo(update.callback_query.from_user.id, image_data,
                             caption=f"Описание товара:\n{description}", reply_markup=InlineKeyboardMarkup(keyboard))
        host, port = get_host_port(context.user_data)
        db = get_database_connection(host, port)
        db.set(str(update.callback_query.from_user.id)*2, query.data)
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


def indicate_weight(update, context):
    global strapi_token
    users_reply = update.message.text
    host, port = get_host_port(context.user_data)
    db = get_database_connection(host, port)
    product_id = db.get(str(update.message.from_user.id)*2).decode("utf-8")
    update.message.reply_text(f"{users_reply}\nHost {host}\nPort {port}\n{product_id}")
    try:
        headers = {'Authorization': f'Bearer {strapi_token}'}
        params = {
            'data': {
                'product': product_id,
                'quantity': users_reply,
                'user_id':  f"{update.message.from_user.id}",
            }
        }
        response = requests.post('http://localhost:1337/api/user-orders/',
                                 headers=headers, json=params)
        response.raise_for_status()
        return "HANDLE_DESCRIPTION"
    except Exception as err:
        return "START"

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
        'START_MENU': main_menu_button,
        'HANDLE_DESCRIPTION': product_choise_button,
        'HANDLE_USER_ORDER': process_orders,
        'ECHO': indicate_weight
    }
    state_handler = states_functions[user_state]
    # Если вы вдруг не заметите, что python-telegram-bot перехватывает ошибки.
    # Оставляю этот try...except, чтобы код не падал молча.
    # Этот фрагмент можно переписать.
    try:
        context.user_data[str(port)] = host
        next_state = state_handler(update, context)
        logger.info("next_state "+next_state)
        db.set(chat_id, next_state)
    except requests.exceptions.ConnectionError:
        update.callback_query.message.reply_text("Нет соединения с БД. Магазин не работает 🤷‍♂️")
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
