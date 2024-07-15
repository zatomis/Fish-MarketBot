from urllib.error import URLError
from io import BytesIO
import phonenumbers
import requests
from environs import Env
import redis
from functools import partial
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Filters, Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


_database = None
strapi_token = ''


def delete_order_item(item_id):
    # удалить позицию из заказа
    global strapi_token
    headers = {'Authorization': f'Bearer {strapi_token}'}
    url = f"http://localhost:1337/api/user-orders/{item_id}"
    response = requests.delete(url, headers=headers)
    response.raise_for_status()


def clear_user_orders(user_id):
    headers = {'Authorization': f'Bearer {strapi_token}'}
    params = {
        'populate': 'product',
        'filters[user_id]][$eq]': user_id,
    }
    response = requests.get('http://localhost:1337/api/user-orders/',
                            headers=headers, params=params)
    response.raise_for_status()
    user_orders = response.json()['data']
    if user_orders:
        for order in user_orders:
            delete_order_item(order['id'])


def change_user_orders(user_id, cart_id):
    # получить список всех заказов, отфильтровав их по user_id
    headers = {'Authorization': f'Bearer {strapi_token}'}
    params = {
        'filters[user_id]][$eq]': user_id,
    }
    response = requests.get('http://localhost:1337/api/user-orders/',
                            headers=headers, params=params)
    response.raise_for_status()
    user_product_ids = []
    user_orders = response.json()['data']
    for order in user_orders:
        user_product_ids.append(order['id'])
    # заменить поле user_id
    headers = {'Authorization': f'Bearer {strapi_token}'}
    for product in user_product_ids:
        data = {
            'data': {
                'user_id': f"{user_id}-{cart_id}"
            }
        }
        response = requests.put(f'http://localhost:1337/api/user-orders/{product}', headers=headers, json=data)
        response.raise_for_status()


def delete_cart_by_id(item_id):
    # удалить корзину
    global strapi_token
    headers = {'Authorization': f'Bearer {strapi_token}'}
    url = f"http://localhost:1337/api/carts/{item_id}"
    response = requests.delete(url, headers=headers)
    response.raise_for_status()


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
        [InlineKeyboardButton("О магазине...", callback_data="about")],
    ]
    return InlineKeyboardMarkup(keyboard)


def products_menu():
    global strapi_token
    products = get_products(strapi_token)
    buttons = []
    for product in products['data']:
        buttons.append(
            [
                InlineKeyboardButton(text=product['attributes']['Title'], callback_data=product['id']),
                InlineKeyboardButton(text=str(product['attributes']['Price'])+"💰", callback_data=product['id'])
            ]
        )
    buttons.append([InlineKeyboardButton(text="⬅️ назад", callback_data='0')])
    return InlineKeyboardMarkup(buttons)


def start(update: Update, context: CallbackContext):
    update.message.reply_text('Бот Магазин - "Рыба Моя"🐟', reply_markup=main_menu())
    logger.info(update.message.message_id)
    return "START_MENU"


def get_user_phone(update: Update, context: CallbackContext) -> None:
    global strapi_token
    host, port = get_host_port(context.user_data)
    db = get_database_connection(host, port)
    phone = update.message.text
    cart_id = db.get(f"{update.message.from_user.id}-2").decode("utf-8")
    user_mail = db.get(f"{update.message.from_user.id}-3").decode("utf-8")
    if phone.lower() == "отмена":
        update.message.reply_text(f'Бот Магазин - "Рыба Моя"🐟', reply_markup=main_menu())
        # удалить корзину из заказов, но оставить заказные позиции юзера
        delete_cart_by_id(cart_id)
        return "START_MENU"
    else:
        # только будут цифры
        phone = ''.join(re.findall(r'-[0-9]+|[0-9]+', phone))
        user_phone = phonenumbers.is_valid_number(phonenumbers.parse(phone, "RU"))
        if user_phone:
            info = f"Спасибо за заказ. С вами свяжутся в ближайщее время!\n" \
                   f"Ваш заказ №{cart_id}\n" \
                   f"Ваш номер телефона {phone}\n" \
                   f"Почта {user_mail}"
            # изменить заказные позиции юзера, т.е. они будут в корзине и их не будет в заказах
            change_user_orders(update.message.from_user.id, cart_id)
            # создать контакт с привязкой к корзине заказов
            headers = {'Authorization': f'Bearer {strapi_token}'}
            # cart = {
            #     'connect': cart_id
            # }
            params = {
                'data': {
                    'Mail': user_mail,
                    'Phone': phone,
                    'carts': cart_id,
                    'Full_name': f"{update.message.from_user.full_name} {update.message.from_user.first_name}",
                }
            }
            response = requests.post('http://localhost:1337/api/contacts/',
                                     headers=headers, json=params)
            response.raise_for_status()



            update.message.reply_text(f'Бот Магазин - "Рыба Моя"🐟\n{info}', reply_markup=main_menu())
            return "START_MENU"

        else:
            update.message.reply_text("Не верный номер. Пробуйте заново или напишите/отправьте боту слово Отмена")
            return "GET_PHONE"


def get_user_mail(update: Update, context: CallbackContext) -> None:
    global strapi_token
    from email.utils import parseaddr
    host, port = get_host_port(context.user_data)
    db = get_database_connection(host, port)
    address = update.message.text
    if address.lower() == "отмена":
        update.message.reply_text(f'Бот Магазин - "Рыба Моя"🐟', reply_markup=main_menu())
        # удалить корзину заказов
        cart_id = db.get(f"{update.message.from_user.id}-2").decode("utf-8")
        delete_cart_by_id(cart_id)
        return "START_MENU"
    else:
        email_regex = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
        is_valid = email_regex.fullmatch(address)
        parsed_email = parseaddr(address)[1]
        if (is_valid is not None and parsed_email == address):
            # сохранить адрес почты
            db.set(f"{update.message.from_user.id}-3", address)
            update.message.reply_text("Укажите ваш телефон")
            return "GET_PHONE"
        else:
            update.message.reply_text("Не верный адрес. Пробуйте заново или напишите/отправьте боту слово Отмена")
            return "GET_MAIL"


def cart_choise_yes_no_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if int(query.data) > 0:
        delete_order_item(query.data)
    query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
    query.bot.send_message(update.callback_query.from_user.id, f'Бот Магазин - "Рыба Моя"🐟', reply_markup=main_menu())
    return "START_MENU"


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
        keyboard = [
            [
                InlineKeyboardButton("Да", callback_data=query.data),
                InlineKeyboardButton("Нет", callback_data="0"),
            ],
        ]
        global strapi_token
        headers = {'Authorization': f'Bearer {strapi_token}'}
        params = {'populate': 'product'}
        url = f'http://localhost:1337/api/user-orders/{query.data}'
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        user_order = response.json()
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
        query.bot.send_message(update.callback_query.from_user.id,
                               f"Вы хотите удалить позицию:\n"
                               f"{user_order['data']['attributes']['product']['data']['attributes']['Title']} "
                               f"в кол-ве {user_order['data']['attributes']['quantity']}",
                               reply_markup=reply_markup)
        return "CART_MENU_CHOISE"
    else:
        match query.data:
            case '0':
                # создать новую и добавить связи
                headers = {'Authorization': f'Bearer {strapi_token}'}
                params = {
                    'data': {
                        'populate': 'User_orders',
                        'cart_id': f"{update.callback_query.message.from_user.id}",
                    }
                }
                response = requests.post('http://localhost:1337/api/carts/',
                                         headers=headers, json=params)
                response.raise_for_status()
                cart_id = response.json()['data']['id']
                logger.info(cart_id)
                # получить заказы пользователя и сформировать из них корзину
                params = {
                        'populate': 'product',
                        'filters[user_id]][$eq]': update.callback_query.from_user.id,
                         }
                response = requests.get('http://localhost:1337/api/user-orders/', headers=headers, params=params)
                response.raise_for_status()
                orders = response.json()['data']
                user_orders = []
                if orders:
                    for order in orders:
                        user_orders.append(order['id'])
                    orders = {
                        'connect': user_orders
                    }
                    data = {
                        'data': {
                            'user_orders': orders
                        }
                    }
                    response = requests.put(f'http://localhost:1337/api/carts/{cart_id}', headers=headers, json=data)
                    response.raise_for_status()
                    host, port = get_host_port(context.user_data)
                    db = get_database_connection(host, port)
                    # запомнили кто и какой номер корзины
                    db.set(f"{update.callback_query.from_user.id}-1", update.callback_query.from_user.id)
                    db.set(f"{update.callback_query.from_user.id}-2", cart_id)
                    query.bot.send_message(update.callback_query.from_user.id, 'Укажите ваш Email 📩')
                    return "GET_MAIL"
                else:
                    query.bot.deleteMessage(update.callback_query.from_user.id,
                                            update.callback_query.message.message_id)
                    query.bot.send_message(update.callback_query.from_user.id,
                                           f'Бот Магазин - "Рыба Моя"🐟\nДобавьте товары в корзину‼️',
                                           reply_markup=main_menu())
                    return "START_MENU"
            case '-1':
                query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
                query.bot.send_message(update.callback_query.from_user.id, f'Бот Магазин - "Рыба Моя"🐟',
                                       reply_markup=main_menu())
                return "START_MENU"


def main_menu_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    match query.data:
        case 'product_list':
            query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
            query.bot.send_message(update.callback_query.from_user.id, 'Список товаров!', reply_markup=products_menu())
            return "HANDLE_MENU"
        case 'my_cart':
            # показать позиции заказа пользователя с ценами, корзину итоговую формировать по кнопке К оформлению
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
                    position_total = order['attributes']['quantity']*\
                                     order['attributes']['product']['data']['attributes']['Price']
                    buttons.append(
                        [
                            InlineKeyboardButton(text=order['attributes']['product']['data']['attributes']['Title'],
                                                 callback_data=str(order['id'])),
                            InlineKeyboardButton(text=f"{order['attributes']['quantity']}x"
                                                      f"{order['attributes']['product']['data']['attributes']['Price']}="
                                                      f"{position_total}"'❌',
                                                 callback_data=str(order['id'])),
                         ]
                    )
                    order_price = order_price + position_total
                buttons.append([InlineKeyboardButton(text='Оформить заказ', callback_data='0')])
                buttons.append([InlineKeyboardButton(text='Главное меню', callback_data='-1')])
                reply_markup = InlineKeyboardMarkup(buttons)
                query.bot.send_message(update.callback_query.from_user.id,
                                       f'Итого по заказу {order_price}',
                                       reply_markup=reply_markup)
                return "HANDLE_USER_ORDER"
            else:
                query.bot.send_message(update.callback_query.from_user.id, f'Корзина пуста 🤷\nИспользуйте список товаров', reply_markup=main_menu())
            return "START_MENU"

        case 'clear_cart':
            clear_user_orders(update.callback_query.from_user.id)
            query.bot.send_message(update.callback_query.from_user.id, f'Корзина пуста 🤷\nИспользуйте список товаров')
            return "START_MENU"

        case 'about':
            query.bot.send_message(update.callback_query.from_user.id, f'Хороший магазин...')
            return "START_MENU"


def product_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    try:
        if query.data == '0':
            query.bot.deleteMessage(update.callback_query.from_user.id, update.callback_query.message.message_id)
            query.bot.send_message(update.callback_query.from_user.id, f'Бот Магазин - "Рыба Моя"🐟',
                                   reply_markup=main_menu())
            return "START_MENU"
        else:
            global strapi_token
            product_title = get_products(strapi_token, query.data, getimage=True)
            picture_url = 'http://localhost:1337' +\
                          product_title['data']['attributes']['Picture']['data'][0]['attributes']['url']
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
                                 caption=f"Описание товара:\n{description}",
                                 reply_markup=InlineKeyboardMarkup(keyboard))
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


def indicate_weight(update, context):
    global strapi_token
    tmpl = '^[1-9][0-9]*$'
    users_reply = update.message.text
    if re.match(tmpl, users_reply) is not None:
        host, port = get_host_port(context.user_data)
        db = get_database_connection(host, port)
        product_id = db.get(str(update.message.from_user.id) * 2).decode("utf-8")
        try:
            headers = {'Authorization': f'Bearer {strapi_token}'}
            params = {
                'data': {
                    'product': product_id,
                    'quantity': users_reply,
                    'user_id': f"{update.message.from_user.id}",
                }
            }
            response = requests.post('http://localhost:1337/api/user-orders/',
                                     headers=headers, json=params)
            response.raise_for_status()
            update.message.reply_text("Позиция добавлена в корзину☑️\n👆Используйте меню выше для продолжения")
            return "HANDLE_DESCRIPTION"
        except Exception as err:
            return "START"
    else:
        update.message.reply_text("Не верно указан вес!")
        return "ECHO"


def handle_users_reply(update, context, host, port):
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
        'CART_MENU_CHOISE': cart_choise_yes_no_button,
        'GET_MAIL': get_user_mail,
        'GET_PHONE': get_user_phone,
        'ECHO': indicate_weight
    }
    state_handler = states_functions[user_state]
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
