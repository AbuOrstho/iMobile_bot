from aiogram import types
from aiogram.dispatcher import Dispatcher
from handlers.keyboards import *
from services.cart_db import add_to_cart, get_cart, get_cart_count, remove_from_cart

user_choice = {}
category_display = {
    "АКСЕССУАРЫ": "аксессуар  ",
    "НАУШНИКИ": "наушников",
    "НОУТБУКИ": "ноутбука ",
    "ПЛАНШЕТЫ": "планшета ",
    "СМАРТ ЧАСЫ": "смарт-часов",
    "СМАРТФОНЫ": "смартфона ",
}


async def category_callback_handler(callback_query: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку товара."""
    category_name = callback_query.data.replace("category_", "")
    keyboard = create_manufacturer_keyboard(category_name)
    if len(keyboard["inline_keyboard"]) > 1:
        # print(keyboard)
        await callback_query.message.edit_text(f"Выберите производителя {category_display[category_name][:-2]}ов",
                                               reply_markup=keyboard)
    else:
        await callback_query.message.edit_text(
            f"К сожалению, {category_display[category_name][:-2]}ов пока что нет в наличии",
            reply_markup=keyboard)

    await callback_query.answer()  # Подтверждение callback-запроса


async def back_to_category_callback_handler(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("Выберите товар:", reply_markup=create_categories_keyboard())
    await callback_query.answer()  # Подтверждение callback-запроса


async def model_callback_handler(callback_query: types.CallbackQuery):
    """
    Функция для обработки выбора производителя и изменения сообщения и кнопок на доступные модели
    :param callback_query:
    :return:
    """
    data_list = callback_query.data.split('_')
    category_name, manufacturer = data_list[1], data_list[2]

    keyboard = create_models_keyboard(category_name, manufacturer)

    if len(keyboard["inline_keyboard"]) > 1:
        # print(keyboard)
        await callback_query.message.edit_text(f"Выберите модель {category_display[category_name]} от {manufacturer}",
                                               reply_markup=keyboard)
    else:
        await callback_query.message.edit_text(
            f"К сожалению, {category_display[category_name]} от {manufacturer} пока что нет в наличии",
            reply_markup=keyboard)

    await callback_query.answer()  # Подтверждение callback-запроса


async def back_to_manufacturer_callback_handler(callback_query: types.CallbackQuery):
    # Удаляем старое сообщение с фото
    await callback_query.message.delete()


async def add_to_cart_callback_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    product_id = callback_query.data.split('_')[-1]
    if get_cart_count(user_id) < 50:
        print(user_id, product_id)
        add_to_cart(user_id, product_id)
        await callback_query.answer("Товар успешно добавлен в корзину", show_alert=True)
    else:
        await callback_query.answer("Ваша корзина переполнена. Пожалуйста, удалите лишние товары и попробуйте снова.",
                                    show_alert=True)


async def get_cart_items(message: types.Message):
    user_id = message.from_user.id
    cart_items = get_cart(user_id)

    cart_category_display = {
        "АКСЕССУАРЫ": "Аксессуар",
        "НАУШНИКИ": "Наушники",
        "НОУТБУКИ": "Ноутбук",
        "ПЛАНШЕТЫ": "Планшет ",
        "СМАРТ ЧАСЫ": "Смарт-часы",
        "СМАРТФОНЫ": "Смартфон",
    }

    cart_dict = {}
    response_text = ""

    if cart_items:
        response_text += "🛒 Ваша корзина:\n"
        for index, product_id in enumerate(cart_items, start=1):
            product_info = db.get_product_by_id(product_id)

            cart_dict[index] = {
                "id": product_info["id"],
                "category": product_info['category'],
                "manufacturer": product_info["manufacturer"],
                "short_name": product_info["short_name"],
                "description": product_info["description"],
                "memory": product_info["memory"],
                "color": product_info["color"],
                "price": product_info["price"],
            }

            response_text += (
                f"<b>/{index}</b>: {cart_category_display.get(product_info['category'], 'Товар')} {cart_dict[index]['manufacturer']} "
                f"{cart_dict[index]['short_name']} {cart_dict[index]['color']} "
                f"{cart_dict[index]['memory'] if cart_dict[index]['memory'] != 0 else ''}\nЦена: <b>{int(cart_dict[index]['price'])} ₽</b>\n\n")

        markup = get_pagination_keyboard(user_id, cart_dict, 0)

        await message.answer(
            response_text + "\n\nЧтобы удалить товар из корзины, пожалуйста, нажмите на одну из кнопок ниже, соответствующую его индексу. "
                            "\nДля полной очистки корзины нажмите на /clear_cart.",
            parse_mode="HTML",
            reply_markup=markup
        )
    else:
        await message.answer("🛒 Ваша корзина пуста.", parse_mode="HTML")


def get_pagination_keyboard(user_id, cart_dict, page=0):
    markup = InlineKeyboardMarkup(row_width=5)

    start = page * 10
    end = start + 10

    for index in range(start, min(end, len(cart_dict))):
        product_id = cart_dict[index + 1]["id"]
        markup.insert(InlineKeyboardButton(
            text=f"{index + 1}",
            callback_data=f"delete_product_{user_id}_{product_id}"
        ))

    navigation_buttons = []
    if start > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"cart_page_{user_id}_{page - 1}"))
    if end < len(cart_dict):
        navigation_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"cart_page_{user_id}_{page + 1}"))

    if navigation_buttons:
        markup.row(*navigation_buttons)

    return markup


async def delete_product_callback_handler(callback_query: types.CallbackQuery):
    """Обрабатывает удаление товара из корзины."""
    user_id = callback_query.from_user.id
    _, _, product_id = callback_query.data.split('_', 2)

    remove_from_cart(user_id, int(product_id))
    await callback_query.answer("Товар удален из корзины", show_alert=True)
    await get_cart_items(callback_query.message)


async def paginate_cart_callback_handler(callback_query: types.CallbackQuery):
    """Обрабатывает переключение страниц корзины."""
    user_id = callback_query.from_user.id
    _, _, page = callback_query.data.rsplit('_', 2)

    cart_items = get_cart(user_id)
    cart_dict = {index + 1: db.get_product_by_id(product_id) for index, product_id in enumerate(cart_items)}

    markup = get_pagination_keyboard(user_id, cart_dict, int(page))
    await callback_query.message.edit_reply_markup(reply_markup=markup)
    await callback_query.answer()


def register_callback_handlers(dp: Dispatcher):
    """Регистрирует обработчики callback-запросов."""
    dp.register_callback_query_handler(category_callback_handler,
                                       lambda callback_query: callback_query.data.startswith("category_"))
    dp.register_callback_query_handler(back_to_category_callback_handler,
                                       lambda callback_query: callback_query.data.startswith("back_to_categories"))
    dp.register_callback_query_handler(model_callback_handler,
                                       lambda callback_query: callback_query.data.startswith("manufacturer_"))
    dp.register_callback_query_handler(back_to_manufacturer_callback_handler,
                                       lambda callback_query: callback_query.data.startswith("back_to_manufacturer_"))
    dp.register_callback_query_handler(add_to_cart_callback_handler,
                                       lambda callback_query: callback_query.data.startswith("add_to_cart_"))
    dp.register_callback_query_handler(delete_product_callback_handler,
                                       lambda callback_query: callback_query.data.startswith("delete_product_"))
    dp.register_callback_query_handler(paginate_cart_callback_handler,
                                       lambda callback_query: callback_query.data.startswith("cart_page_"))


"""
{'id': 44, 
'category': 'СМАРТФОНЫ', 
'manufacturer': 'Apple', 
'short_name': '15 Pro Max', 
'name': 'Смартфон Apple iPhone 15 Pro Max 256GB White Titanium (Титановый белый)', 
'description': nan, 
'memory': '256Gb', 
'color': 'Titanium (Титановый белый)', 
'price': 130900.0, 
'stock': 1.0, 
'photo': 'https://imobile77.ru/wa-data/public/shop/products/27/08/10827/images/41105/41105.200.png'}
"""
