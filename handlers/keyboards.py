from itertools import product

from aiogram.types import ReplyKeyboardMarkup, CallbackQuery, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from services.database import db


def create_start_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает и возвращает стартовую клавиатуру для главного меню.

    Клавиатура включает кнопки:
    - "Товары" — просмотр доступных товаров.
    - "Сайт" — переход на сайт компании.
    - "Контакты" — информация о способах связи.
    - "О компании" — информация о компании.
    - "Реквизиты" — юридическая информация.

    :return: Объект ReplyKeyboardMarkup с кнопками главного меню.
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Товары", "Сайт", "Контакты", "О компании", "Реквизиты", "Корзина")
    return kb


def create_categories_keyboard() -> InlineKeyboardMarkup:
    """
    Создает и возвращает inline-клавиатуру с уникальными категориями товаров.

    Данные о категориях получаются из базы данных с помощью метода `db.get_unique_categories()`.
    Каждая категория представлена отдельной кнопкой с callback_data вида `category_<название категории>`.

    :return: Объект InlineKeyboardMarkup с кнопками категорий товаров.
    """
    keyboard = InlineKeyboardMarkup(row_width=3)
    for category in db.get_unique_categories():
        keyboard.insert(InlineKeyboardButton(category, callback_data=f"category_{category}"))
    return keyboard


def create_manufacturer_keyboard(category_name: str) -> InlineKeyboardMarkup:
    """
    Создает и возвращает inline-клавиатуру с производителями товаров в выбранной категории.

    Данные о производителях получаются из базы данных с помощью `db.get_unique_manufacturers(category_name)`.
    Каждая кнопка имеет callback_data вида `manufacturer_<название категории>_<производитель>`.
    Включает кнопку "Назад" для возврата к выбору категорий.

    :param category_name: Название категории товара (например, 'СМАРТФОНЫ', 'ПЛАНШЕТЫ', 'НАУШНИКИ').
    :return: Объект InlineKeyboardMarkup с кнопками производителей в указанной категории.
    """
    keyboard = InlineKeyboardMarkup(row_width=3)
    for manufacturer in db.get_unique_manufacturers(category_name):
        keyboard.insert(
            InlineKeyboardButton(manufacturer, callback_data=f"manufacturer_{category_name}_{manufacturer}"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_categories"))
    return keyboard


def create_models_keyboard(category_name: str, manufacturer: str) -> InlineKeyboardMarkup:
    """
    Создает и возвращает inline-клавиатуру с моделями товаров в выбранной категории.

    Данные о производителях получаются из базы данных с помощью `db.get_unique_manufacturers(category_name)`.
    Каждая кнопка имеет callback_data вида `manufacturer_<название категории>_<производитель>`.
    Включает кнопку "Назад" для возврата к выбору категорий.

    :param category_name: Название категории товара (например, 'СМАРТФОНЫ', 'ПЛАНШЕТЫ', 'НАУШНИКИ').
    :return: Объект InlineKeyboardMarkup с кнопками производителей в указанной категории.
    """

    models_by_manufacturer = db.get_models_by_manufacturer(category_name, manufacturer)

    keyboard = InlineKeyboardMarkup(row_width=3)
    for model in models_by_manufacturer:
        models_name = "_".join(str(model).split(' '))
        keyboard.insert(InlineKeyboardButton(model, callback_data=f"model_{models_name}"))
    keyboard.add(InlineKeyboardButton("Назад", callback_data=f"category_{category_name}"))
    return keyboard


def create_product_configuration(product_configuration, models_name: str, color_index: int, memory_index: int):
    """
    Создаёт клавиатуру выбора цвета и памяти для конкретной модели
    с учётом того, что product_configuration уже отфильтрован по stock>0.
    """
    # Если товар полностью отфильтрован (нет на складе):
    if not product_configuration:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Нет в наличии", callback_data="out_of_stock"))
        return keyboard

    keyboard = InlineKeyboardMarkup(row_width=3)
    colors = list(product_configuration.keys())
    # А дальше — как в вашем коде. Например:
    color = colors[color_index]
    memory_sizes = list(product_configuration[color].keys())
    memory = memory_sizes[memory_index]

    product_data = product_configuration[color][memory]
    product_id = product_data["id"]
    # и т.д.

    # Здесь не забывайте, что если у товара stock > 0, значит мы можем добавить кнопки:
    keyboard.insert(InlineKeyboardButton("⬅️", callback_data=f"previous_color_{models_name.replace(' ', '_')}"))
    keyboard.insert(InlineKeyboardButton("Цвет", callback_data="color_ignor"))
    keyboard.insert(InlineKeyboardButton("➡️", callback_data=f"next_color_{models_name.replace(' ', '_')}"))

    # То же самое для памяти...
    keyboard.insert(InlineKeyboardButton("⬅️", callback_data=f"previous_memory_{models_name.replace(' ', '_')}"))
    keyboard.insert(InlineKeyboardButton("Память", callback_data="memory_ignor"))
    keyboard.insert(InlineKeyboardButton("➡️", callback_data=f"next_memory_{models_name.replace(' ', '_')}"))

    # Кнопки "Купить" и "В корзину"
    keyboard.add(InlineKeyboardButton("Купить", callback_data=f"buy_{product_id}"))
    keyboard.insert(InlineKeyboardButton("В Корзину", callback_data=f"add_to_cart_{product_id}"))

    # Кнопка "Назад"
    manufacturer = product_data["manufacturer"]
    keyboard.add(InlineKeyboardButton("Назад", callback_data=f"back_to_manufacturer_{manufacturer}"))

    return keyboard


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

# card_information = db.get_product_configuration('16 Pro Max')
# print(create_product_configuration(card_information, '16 Pro Max', 0, 0))
