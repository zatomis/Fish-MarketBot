import requests


def get_products(url, token, product_id='', getimage=False):
    headers = {'Authorization': f'Bearer {token}'}
    if getimage:
        params = {'populate': 'Picture'}
    response = requests.get(f'{url}/api/Products/{product_id}', headers=headers, params=params)
    response.raise_for_status()
    return response.json()


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
            delete_order_item(url, order['id'])


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
