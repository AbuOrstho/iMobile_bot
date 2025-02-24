import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import Message
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import TOKEN
from handlers.answer import answers, answer

from handlers.keyboards import create_start_keyboard, create_categories_keyboard, create_product_configuration
from handlers.callbacks import register_callback_handlers, user_choice, get_cart_items
from services.database import db

from services.cart_db import *

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=storage)
ADMIN_ID = 1338143348

class BroadcastState(StatesGroup):
    waiting_for_media_type = State()
    waiting_for_media = State()
    waiting_for_caption = State()
    waiting_for_send_or_schedule = State()
    waiting_for_schedule_time = State()

@dp.message_handler(commands=["start"])
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else "None"
    first_name = message.from_user.first_name if message.from_user.first_name else "None"
    last_name = message.from_user.last_name if message.from_user.last_name else "None"

    add_user(user_id, username, first_name, last_name)

    start_text = (
        "Привет! Добро пожаловать в наш магазин техники.\n\n"
        "Здесь вы можете найти различные товары и совершить покупку.\n\n"
        "Приятного пользования!"
    )
    await message.answer(start_text, reply_markup=create_start_keyboard())


@dp.message_handler(commands=['clear_cart'])
async def cart_command(message: Message):
    clear_cart(message.from_user.id)


@dp.message_handler(commands=["broadcast"])
async def broadcast_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("Фото", callback_data="media_photo"),
        InlineKeyboardButton("Видео", callback_data="media_video"),
        InlineKeyboardButton("Документ", callback_data="media_document"),
        InlineKeyboardButton("Текст", callback_data="media_text")
    ]
    keyboard.add(*buttons)

    await message.answer("Выберите тип контента для рассылки:", reply_markup=keyboard)
    await BroadcastState.waiting_for_media_type.set()


@dp.callback_query_handler(state=BroadcastState.waiting_for_media_type)
async def choose_media_type(callback_query: types.CallbackQuery, state: FSMContext):
    media_type = callback_query.data.split("_", maxsplit=1)[1]
    await state.update_data(media_type=media_type)
    await bot.send_message(callback_query.from_user.id, "Теперь отправьте файл или текстовое сообщение.")
    await BroadcastState.waiting_for_media.set()


@dp.message_handler(
    state=BroadcastState.waiting_for_media,
    content_types=[types.ContentType.PHOTO, types.ContentType.VIDEO, types.ContentType.DOCUMENT, types.ContentType.TEXT]
)
async def receive_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    media_type = data.get("media_type")

    if media_type == "photo":
        await state.update_data(media=message.photo[-1].file_id)
    elif media_type == "video":
        await state.update_data(media=message.video.file_id)
    elif media_type == "document":
        await state.update_data(media=message.document.file_id)
    else:
        # Текст
        await state.update_data(media=message.text)

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Добавить описание", callback_data="add_caption"),
        InlineKeyboardButton("Нет", callback_data="skip_caption")
    )
    await message.answer("Хотите добавить описание?", reply_markup=keyboard)
    await BroadcastState.waiting_for_caption.set()


@dp.callback_query_handler(state=BroadcastState.waiting_for_caption)
async def process_caption_choice(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "add_caption":
        await bot.send_message(
            callback_query.from_user.id,
            "Введите описание (или 'stop' для пропуска):"
        )
        # Остаёмся в том же состоянии (waiting_for_caption)
        # и ждём текст от пользователя
    else:
        # Пользователь выбрал «Нет»
        await state.update_data(caption="")
        await ask_send_or_schedule(callback_query.message, state)


@dp.message_handler(state=BroadcastState.waiting_for_caption, content_types=types.ContentType.TEXT)
async def receive_caption(message: types.Message, state: FSMContext):
    if message.text.lower() == "stop":
        await state.update_data(caption="")
    else:
        await state.update_data(caption=message.text)

    await ask_send_or_schedule(message, state)


async def ask_send_or_schedule(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Отправить сейчас", callback_data="send_now"),
        InlineKeyboardButton("Запланировать", callback_data="schedule")
    )
    await message.answer("Когда отправить рассылку?", reply_markup=keyboard)
    await BroadcastState.waiting_for_send_or_schedule.set()


@dp.callback_query_handler(state=BroadcastState.waiting_for_send_or_schedule)
async def schedule_or_send(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "send_now":
        # Немедленная отправка
        await send_broadcast(state)
        await state.finish()
    else:
        # Планирование
        await bot.send_message(callback_query.from_user.id, "Введите дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ")
        await BroadcastState.waiting_for_schedule_time.set()


@dp.message_handler(state=BroadcastState.waiting_for_schedule_time, content_types=types.ContentType.TEXT)
async def schedule_broadcast(message: types.Message, state: FSMContext):
    try:
        # 1) Парсим дату
        schedule_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        delay = (schedule_time - datetime.now()).total_seconds()
        if delay < 0:
            await message.answer("Указанное время уже прошло. Укажите будущую дату.")
            return

        # 2) Сохраняем данные в локальную переменную (чтобы не потерять при finish)
        data = await state.get_data()

        # 3) Выходим из состояния (данные в state будут утеряны!)
        await state.finish()

        await message.answer(f"Рассылка запланирована на {message.text}!")

        # 4) Спим до указанного времени
        await asyncio.sleep(delay)

        # 5) Отправляем
        await real_scheduled_broadcast(data)

    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте ещё раз (ГГГГ-ММ-ДД ЧЧ:ММ).")


async def real_scheduled_broadcast(data: dict):
    """
    Функция, отправляющая рассылку по запланированному времени,
    используя сохранённые данные (media_type, media, caption).
    """
    user_count, user_ids = get_users_info()
    media_type = data.get("media_type")
    media = data.get("media")
    caption = data.get("caption", "")

    success_count = 0
    for user_id in user_ids:
        try:
            if media_type == "photo":
                await bot.send_photo(user_id, media, caption=caption)
            elif media_type == "video":
                await bot.send_video(user_id, media, caption=caption)
            elif media_type == "document":
                await bot.send_document(user_id, media, caption=caption)
            else:
                await bot.send_message(user_id, media)
            success_count += 1
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение {user_id}: {e}")

    await bot.send_message(
        ADMIN_ID,
        f"Рассылка завершена! Успешно отправлено: {success_count} из {user_count}"
    )


async def send_broadcast(state: FSMContext):
    """
    Мгновенная отправка рассылки, без планирования.
    """
    data = await state.get_data()
    user_count, user_ids = get_users_info()
    media_type = data.get("media_type")
    media = data.get("media")
    caption = data.get("caption", "")

    success_count = 0
    for user_id in user_ids:
        try:
            if media_type == "photo":
                await bot.send_photo(user_id, media, caption=caption)
            elif media_type == "video":
                await bot.send_video(user_id, media, caption=caption)
            elif media_type == "document":
                await bot.send_document(user_id, media, caption=caption)
            else:
                await bot.send_message(user_id, media)
            success_count += 1
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение {user_id}: {e}")

    await bot.send_message(
        ADMIN_ID,
        f"Рассылка завершена! Успешно отправлено: {success_count} из {user_count}"
    )

@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith("model_"))
async def model_configuration_handler(callback_query: types.CallbackQuery):
    model_name = callback_query.data[len("model_"):].replace("_", " ")
    user_id, chat_id = callback_query.from_user.id, callback_query.message.chat.id
    user_choice[user_id] = [0, 0]

    card_information = db.get_product_configuration(model_name)
    color_index, memory_index = user_choice[user_id]

    colors = list(card_information.keys())
    color = colors[color_index]
    memory_sizes = list(card_information[color].keys())
    memory = memory_sizes[memory_index]

    product_data = card_information[color][memory]
    photo, name, description, price = map(product_data.get, ["photo", "name", "description", "price"])

    keyboard = create_product_configuration(card_information, model_name, color_index, memory_index)

    text = f"""{name}\n\n{description}\nЦвет: {color}\n{f'Память: {memory}' if memory else ''}\nЦена: {int(price)} ₽"""

    await bot.send_photo(chat_id=chat_id, photo=photo, caption=text, reply_markup=keyboard)
    await callback_query.answer()


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith("buy_"))
async def buy_callback_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    product_id = callback_query.data.split('_')
    print(int(product_id[-1]))
    product_info = db.get_product_by_id(int(product_id[-1]))
    cart_category_display = {
        "АКСЕССУАРЫ": "Аксессуар",
        "НАУШНИКИ": "Наушники",
        "НОУТБУКИ": "Ноутбук",
        "ПЛАНШЕТЫ": "Планшет ",
        "СМАРТ ЧАСЫ": "Смарт-часы",
        "СМАРТФОНЫ": "Смартфон",
    }

    text_info = f"""
Пользователь @{callback_query.from_user.username} хочет заказать {cart_category_display[product_info['category']]}
{product_info['manufacturer']} {product_info['short_name']} {product_info['color']}
{product_info['memory'] if product_info['memory'] != 0 else ''}\nЦена: <b>{int(product_info['price'])} ₽</b>\nid: <b>{int(product_info['id'])}</b>
"""

    await bot.send_message(chat_id=ADMIN_ID, text=text_info, parse_mode='HTML')
    await callback_query.message.answer('Для заказа свяжитесь с нашим менеджером @Abu_Alonse')


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith("model_") or any(
    callback_query.data.startswith(prefix) for prefix in
    ["previous_color_", "next_color_", "previous_memory_", "next_memory_"]))
async def model_configuration_handler(callback_query: types.CallbackQuery):
    user_id, chat_id, message_id = callback_query.from_user.id, callback_query.message.chat.id, callback_query.message.message_id
    data = callback_query.data

    if data.startswith("model_"):
        model_name = data[len("model_"):].replace("_", " ")
    else:
        parts = data.split("_")
        model_name = "_".join(parts[2:]).replace("_", " ")
        action = parts[0]  # previous или next
        category = parts[1]  # color или memory

        # Обновляем выбор пользователя
        if user_id in user_choice:
            if category == "color":
                color_count = len(db.get_product_configuration(model_name).keys())
                if color_count > 1:
                    if action == "next":
                        user_choice[user_id][0] = (user_choice[user_id][0] + 1) % color_count
                    else:
                        user_choice[user_id][0] = (user_choice[user_id][0] - 1) % color_count
                else:
                    await callback_query.answer(
                        "К сожалению, сейчас доступен только этот цвет, но ожидается пополнение.", show_alert=True)
            elif category == "memory":
                memory_count = len(db.get_product_configuration(model_name)[
                                       list(db.get_product_configuration(model_name).keys())[0]].keys())
                if memory_count > 1:
                    if action == "next":
                        user_choice[user_id][1] = (user_choice[user_id][1] + 1) % memory_count
                    else:
                        user_choice[user_id][1] = (user_choice[user_id][1] - 1) % memory_count
                else:
                    await callback_query.answer(
                        "К сожалению, сейчас доступен только этот объём, но ожидается пополнение.", show_alert=True)

    # Получаем обновленную информацию о товаре
    card_information = db.get_product_configuration(model_name)
    color_index, memory_index = user_choice.get(user_id, [0, 0])

    colors = list(card_information.keys())
    color = colors[color_index]

    memory_sizes = list(card_information[color].keys())
    memory = memory_sizes[memory_index]

    product_data = card_information[color][memory]
    photo, name, description, price = map(product_data.get, ["photo", "name", "description", "price"])

    keyboard = create_product_configuration(card_information, model_name, color_index, memory_index)
    text = f"""{name}\n\n{description}\nЦвет: {color}\n{f'Память: {memory}' if memory else ''}\nЦена: {int(price)} ₽"""

    # Редактируем существующее сообщение вместо удаления
    await bot.edit_message_media(
        chat_id=chat_id,
        message_id=message_id,
        media=types.InputMediaPhoto(media=photo, caption=text),
        reply_markup=keyboard
    )
    await callback_query.answer()


@dp.message_handler()
async def products_handler(message: Message):
    """Отправляет клавиатуру с товарами в ответ на команду."""
    if message.text == "Товары":
        await message.answer("Выберите товар:", reply_markup=create_categories_keyboard())
    elif message.text == "Корзина":
        await get_cart_items(message)
        # user_id = message.from_user.id
        # cart_items = get_cart(user_id)
        #
        # category_display = {
        #     "АКСЕССУАРЫ": "Аксессуар",
        #     "НАУШНИКИ": "Наушники",
        #     "НОУТБУКИ": "Ноутбук",
        #     "ПЛАНШЕТЫ": "Планшет ",
        #     "СМАРТ ЧАСЫ": "Смарт-часы",
        #     "СМАРТФОНЫ": "Смартфон",
        # }
        #
        # products_dict = {}
        #
        # x = 0
        # if cart_items:
        #     response_text = "🛒 Ваша корзина:\n"
        #     for product_id in cart_items:
        #         products_dict[x] = {
        #
        #         }
        #         x += 1
        #         product_info = db.get_product_by_id(product_id)
        #         response_text += (f"{x}: {category_display[product_info['category']]} {product_info['manufacturer']} "
        #                           f"{product_info['short_name']} {product_info['color']} "
        #                           f"{product_info['memory'] if product_info['memory'] != 0 else ''}\n\n")
        # else:
        #     response_text = "Ваша корзина пуста."
        # await message.answer(response_text)
    elif message.text in answers:
        await message.answer(answer(message.text))


# Регистрируем callback-обработчики
register_callback_handlers(dp)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False)
