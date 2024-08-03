from urllib.error import URLError
from io import BytesIO
import phonenumbers
import requests
from email.utils import parseaddr
from environs import Env
import redis
from functools import partial
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Filters, Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler
import re
from strapi_features import delete_order_item, clear_user_orders, change_user_orders, delete_cart_by_id, get_products, \
    create_user_contact, get_user_order, create_user_order_item, get_cart_id, update_cart, get_user_cart

logger = logging.getLogger(__name__)
_database = None


def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("Список товаров", callback_data="product_list")],
        [InlineKeyboardButton("Моя корзина", callback_data="my_cart")],
        [InlineKeyboardButton("Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton("О магазине...", callback_data="about")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_products_menu(url, token):
    products = get_products(url, token, '', False)
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
    update.message.reply_text('Бот Магазин - "Рыба Моя"🐟', reply_markup=get_main_menu())
    logger.info(update.message.message_id)
    return "START_MENU"


def get_user_phone(update: Update, context: CallbackContext) -> None:
    host = context.bot_data['host']
    port = context.bot_data['port']
    db = get_database_connection(host, port)
    strapi_url = db.get("URL").decode("utf-8")
    strapi_token = db.get("TOKEN").decode("utf-8")
    phone = update.message.text
    cart_id = db.get(f"CARTID{update.message.from_user.id}").decode("utf-8")
    user_mail = db.get(f"MAIL{update.message.from_user.id}").decode("utf-8")
    if phone.lower() == "отмена":
        update.message.reply_text(f'Бот Магазин - "Рыба Моя"🐟', reply_markup=get_main_menu())
        delete_cart_by_id(strapi_url, strapi_token, cart_id)
        return "START_MENU"
    else:
        phone = ''.join(re.findall(r'-[0-9]+|[0-9]+', phone))
        user_phone = phonenumbers.is_valid_number(phonenumbers.parse(phone, "RU"))
        if user_phone:
            info = f"Спасибо за заказ. С вами свяжутся в ближайщее время!\n" \
                   f"Ваш заказ №{cart_id}\n" \
                   f"Ваш номер телефона {phone}\n" \
                   f"Почта {user_mail}"
            change_user_orders(strapi_url, strapi_token, update.message.from_user.id, cart_id)
            create_user_contact(strapi_url, strapi_token, user_mail, phone, cart_id,
                                update.message.from_user.full_name, update.message.from_user.first_name)
            update.message.reply_text(f'Бот Магазин - "Рыба Моя"🐟\n{info}', reply_markup=get_main_menu())
            return "START_MENU"

        else:
            update.message.reply_text("Не верный номер. Пробуйте заново или напишите/отправьте боту слово Отмена")
            return "GET_PHONE"


def get_user_mail(update: Update, context: CallbackContext) -> None:
    host = context.bot_data['host']
    port = context.bot_data['port']
    db = get_database_connection(host, port)
    strapi_url = db.get("URL").decode("utf-8")
    strapi_token = db.get("TOKEN").decode("utf-8")
    address = update.message.text
    if address.lower() == "отмена":
        update.message.reply_text(f'Бот Магазин - "Рыба Моя"🐟', reply_markup=get_main_menu())
        cart_id = db.get(f"CARTID{update.message.from_user.id}").decode("utf-8")
        delete_cart_by_id(strapi_url, strapi_token, cart_id)
        return "START_MENU"
    else:
        email_regex = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
        is_valid = email_regex.fullmatch(address)
        parsed_email = parseaddr(address)[1]
        if is_valid is not None and parsed_email == address:
            db.set(f"MAIL{update.message.from_user.id}", address)
            update.message.reply_text("Укажите ваш телефон")
            return "GET_PHONE"
        else:
            update.message.reply_text("Не верный адрес. Пробуйте заново или напишите/отправьте боту слово Отмена")
            return "GET_MAIL"


def cart_choise_yes_no_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    host = context.bot_data['host']
    port = context.bot_data['port']
    db = get_database_connection(host, port)
    strapi_url = db.get("URL").decode("utf-8")
    strapi_token = db.get("TOKEN").decode("utf-8")
    if int(query.data) > 0:
        delete_order_item(strapi_url, strapi_token, query.data)
    query.bot.send_message(update.callback_query.from_user.id, f'Бот Магазин - "Рыба Моя"🐟', reply_markup=get_main_menu())
    query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
    return "START_MENU"


def product_choise_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    host = context.bot_data['host']
    port = context.bot_data['port']
    db = get_database_connection(host, port)
    strapi_url = db.get("URL").decode("utf-8")
    strapi_token = db.get("TOKEN").decode("utf-8")
    match query.data:
        case 'back':
            query.bot.send_message(update.callback_query.from_user.id, 'Список товаров!', reply_markup=get_products_menu(strapi_url, strapi_token))
            query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
            return "HANDLE_MENU"
        case 'main_menu':
            query.bot.send_message(update.callback_query.from_user.id, 'Главное меню', reply_markup=get_main_menu())
            query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
            return "START_MENU"
        case 'add_cart':
            query.bot.send_message(update.callback_query.from_user.id, 'Укажите вес товара в граммах')
            return "ECHO"


def process_orders(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    host = context.bot_data['host']
    port = context.bot_data['port']
    db = get_database_connection(host, port)
    strapi_url = db.get("URL").decode("utf-8")
    strapi_token = db.get("TOKEN").decode("utf-8")
    if int(query.data) > 0:
        keyboard = [
            [
                InlineKeyboardButton("Да", callback_data=query.data),
                InlineKeyboardButton("Нет", callback_data="0"),
            ],
        ]
        user_order = get_user_order(strapi_url, strapi_token, query.data, 0, False)
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.bot.send_message(update.callback_query.from_user.id,
                               f"Вы хотите удалить позицию:\n"
                               f"{user_order['data']['attributes']['product']['data']['attributes']['Title']} "
                               f"в кол-ве {user_order['data']['attributes']['quantity']}",
                               reply_markup=reply_markup)
        query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
        return "CART_MENU_CHOISE"
    else:
        match query.data:
            case '0':
                cart_id = get_cart_id(strapi_url, strapi_token, update.callback_query.message.from_user.id)
                orders = get_user_order(strapi_url, strapi_token, 0, update.callback_query.from_user.id, True)
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
                    update_cart(strapi_url, strapi_token, cart_id, data)
                    db.set(f"CARTID{update.callback_query.from_user.id}", cart_id)
                    query.bot.send_message(update.callback_query.from_user.id, 'Укажите ваш Email 📩')
                    return "GET_MAIL"
                else:
                    query.bot.send_message(update.callback_query.from_user.id,
                                           f'Бот Магазин - "Рыба Моя"🐟\nДобавьте товары в корзину‼️',
                                           reply_markup=get_main_menu())
                    query.bot.delete_message(update.callback_query.from_user.id,
                                             update.callback_query.message.message_id)
                    return "START_MENU"
            case '-1':
                query.bot.send_message(update.callback_query.from_user.id, f'Бот Магазин - "Рыба Моя"🐟',
                                       reply_markup=get_main_menu())
                query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
                return "START_MENU"


def get_main_menu_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    host = context.bot_data['host']
    port = context.bot_data['port']
    db = get_database_connection(host, port)
    strapi_url = db.get("URL").decode("utf-8")
    strapi_token = db.get("TOKEN").decode("utf-8")
    match query.data:
        case 'product_list':
            query.bot.send_message(update.callback_query.from_user.id, 'Список товаров!', reply_markup=get_products_menu(strapi_url, strapi_token))
            query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
            return "HANDLE_MENU"
        case 'my_cart':
            query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
            orders = get_user_cart(strapi_url, strapi_token, update.callback_query.from_user.id)
            if orders:
                buttons = []
                order_price = 0
                for order in orders:
                    position_total = order['attributes']['quantity'] *\
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
                query.bot.send_message(update.callback_query.from_user.id,
                                       f'Корзина пуста 🤷\nИспользуйте список товаров', reply_markup=get_main_menu())
            return "START_MENU"
        case 'clear_cart':
            clear_user_orders(strapi_url, strapi_token, update.callback_query.from_user.id)
            query.bot.send_message(update.callback_query.from_user.id, f'Корзина пуста 🤷\nИспользуйте список товаров')
            return "START_MENU"

        case 'about':
            query.bot.send_message(update.callback_query.from_user.id, f'Хороший магазин...')
            return "START_MENU"


def get_product_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    host = context.bot_data['host']
    port = context.bot_data['port']
    db = get_database_connection(host, port)
    strapi_url = db.get("URL").decode("utf-8")
    strapi_token = db.get("TOKEN").decode("utf-8")
    try:
        if query.data == '0':
            query.bot.send_message(update.callback_query.from_user.id, f'Бот Магазин - "Рыба Моя"🐟',
                                   reply_markup=get_main_menu())
            query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
            return "START_MENU"
        else:
            product_title = get_products(strapi_url, strapi_token, query.data, getimage=True)
            picture_url = strapi_url +\
                          product_title['data']['attributes']['Picture']['data'][0]['attributes']['url']
            description = product_title['data']['attributes']['Description']
            response = requests.get(picture_url)
            response.raise_for_status()
            image_data = BytesIO(response.content)
            keyboard = [
                [
                    InlineKeyboardButton("Назад", callback_data="back"),
                    InlineKeyboardButton("В корзину", callback_data="add_cart"),
                ],
                [InlineKeyboardButton("Главное меню", callback_data="main_menu")],
            ]
            query.bot.send_photo(update.callback_query.from_user.id, image_data,
                                 caption=f"Описание товара:\n{description}",
                                 reply_markup=InlineKeyboardMarkup(keyboard))
            query.bot.delete_message(update.callback_query.from_user.id, update.callback_query.message.message_id)
            db.set(f"PID{update.callback_query.from_user.id}", query.data)
            return "HANDLE_DESCRIPTION"
    except URLError:
        update.callback_query.message.reply_text('Нет фото')
        return "START"
    except IndexError:
        update.callback_query.message.reply_text('Нет фото')
        return "START"


def indicate_weight(update, context):
    tmpl = '^[1-9][0-9]*$'
    users_reply = update.message.text
    if re.match(tmpl, users_reply) is not None:
        host = context.bot_data['host']
        port = context.bot_data['port']
        db = get_database_connection(host, port)
        strapi_url = db.get("URL").decode("utf-8")
        strapi_token = db.get("TOKEN").decode("utf-8")
        product_id = db.get(f"PID{update.message.from_user.id}").decode("utf-8")
        try:
            create_user_order_item(strapi_url, strapi_token, product_id, users_reply, update.message.from_user.id)
            update.message.reply_text("Позиция добавлена в корзину☑️\n👆Используйте меню выше для продолжения")
            return "HANDLE_DESCRIPTION"
        except Exception as err:
            return "START"
    else:
        update.message.reply_text("Не верно указан вес!")
        return "ECHO"


def handle_users_reply(update, context, host, port):
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
        'HANDLE_MENU': get_product_button,
        'START_MENU': get_main_menu_button,
        'HANDLE_DESCRIPTION': product_choise_button,
        'HANDLE_USER_ORDER': process_orders,
        'CART_MENU_CHOISE': cart_choise_yes_no_button,
        'GET_MAIL': get_user_mail,
        'GET_PHONE': get_user_phone,
        'ECHO': indicate_weight
    }
    state_handler = states_functions[user_state]
    try:
        payload = {
                "host": host,
                "port": port
        }
        context.bot_data.update(payload)
        next_state = state_handler(update, context)
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


def main():
    env = Env()
    env.read_env()
    host = env('REDIS_HOST')
    port = env('REDIS_PORT')
    db = get_database_connection(host, port)
    db.set(f"TOKEN", env.str("STRAPI_TOKEN"))
    db.set(f"URL", env.str("STRAPI_URL"))
    token = env.str("TELEGRAM_TOKEN")
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(partial(handle_users_reply, host=host, port=port)))
    dispatcher.add_handler(MessageHandler(Filters.text, partial(handle_users_reply, host=host, port=port)))
    dispatcher.add_handler(CommandHandler('start', partial(handle_users_reply, host=host, port=port)))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )
    main()
