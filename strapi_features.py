import requests


def delete_order_item(url, token, item_id):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.delete(f"{url}/api/user-orders/{item_id}", headers=headers)
    response.raise_for_status()


def clear_user_orders(url, token, user_id):
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'populate': 'product',
        'filters[user_id]][$eq]': user_id,
    }
    response = requests.get(f'{url}/api/user-orders/',
                            headers=headers, params=params)
    response.raise_for_status()
    user_orders = response.json()['data']
    if user_orders:
        for order in user_orders:
            delete_order_item(url, token, order['id'])


def get_user_order(url, token, data=0, uid=0, filter_uid=False):
    headers = {'Authorization': f'Bearer {token}'}
    params = {'populate': 'product'}
    if not filter_uid:
        response = requests.get(f'{url}/api/user-orders/{data}', headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    else:
        params['filters[user_id]][$eq]'] = uid
        response = requests.get(f'{url}/api/user-orders/', headers=headers, params=params)
        response.raise_for_status()
        return response.json()['data']


def create_user_contact(url, token, user_mail, phone, cart_id, full_name, first_name):
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'data': {
            'Mail': user_mail,
            'Phone': phone,
            'carts': cart_id,
            'Full_name': f"{full_name} {first_name}",
        }
    }
    response = requests.post(f'{url}/api/contacts/',
                             headers=headers, json=params)
    response.raise_for_status()


def change_user_orders(url, token, user_id, cart_id):
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'filters[user_id]][$eq]': user_id,
    }
    response = requests.get(f'{url}/api/user-orders/',
                            headers=headers, params=params)
    response.raise_for_status()
    user_product_ids = []
    user_orders = response.json()['data']
    for order in user_orders:
        user_product_ids.append(order['id'])
    headers = {'Authorization': f'Bearer {token}'}
    for product in user_product_ids:
        data = {
            'data': {
                'user_id': f"{user_id}-{cart_id}"
            }
        }
        response = requests.put(f'{url}/api/user-orders/{product}', headers=headers, json=data)
        response.raise_for_status()


def delete_cart_by_id(url, token, item_id):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.delete(f"{url}/api/carts/{item_id}", headers=headers)
    response.raise_for_status()


def get_products(url, token, product_id='', getimage=False):
    headers = {'Authorization': f'Bearer {token}'}
    params = {}
    if getimage:
        params = {'populate': 'Picture'}
    response = requests.get(f'{url}/api/Products/{product_id}', headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def create_user_order_item(url, token, product_id, quantity, uid):
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'data': {
            'product': product_id,
            'quantity': quantity,
            'user_id': f"{uid}",
        }
    }
    response = requests.post(f'{url}/api/user-orders/',
                             headers=headers, json=params)
    response.raise_for_status()


def get_cart_id(url, token, uid):
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'data': {
            'populate': 'User_orders',
            'cart_id': f"{uid}",
        }
    }
    response = requests.post(f'{url}/api/carts/',
                             headers=headers, json=params)
    response.raise_for_status()
    return response.json()['data']['id']


def update_cart(strapi_url, strapi_token, cart_id, data):
    headers = {'Authorization': f'Bearer {strapi_token}'}
    response = requests.put(f'{strapi_url}/api/carts/{cart_id}', headers=headers, json=data)
    response.raise_for_status()


def get_user_cart(strapi_url, strapi_token, uid):
    headers = {'Authorization': f'Bearer {strapi_token}'}
    params = {
        'populate': 'product',
        'filters[user_id]][$eq]': uid,
    }
    response = requests.get(f'{strapi_url}/api/user-orders/',
                            headers=headers, params=params)
    response.raise_for_status()
    return response.json()['data']
