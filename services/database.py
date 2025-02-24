import pandas as pd

pd.set_option('display.max_colwidth', None)


class ProductDatabase:
    def __init__(self):
        """
        Инициализация базы данных товаров из Excel-файла.
        :param df: Файл .xlsx
        """
        self.df = pd.read_excel("static/DB.xlsx", sheet_name=0)  # Загружаем первый лист
        self.df['short_name'] = self.df['short_name'].astype(str)

    def get_unique_categories(self):
        """
        Получает список всех уникальных категорий товаров.
        :return: Список уникальных категорий
        """
        return self.df['category'].dropna().unique().tolist()

    def get_unique_manufacturers(self, category: str):
        """
        Получает список всех уникальных производителей для указанной категории.
        :param category: Категория товара (например, 'СМАРТФОНЫ', 'ПЛАНШЕТЫ', 'НАУШНИКИ')
        :return: Список уникальных производителей в данной категории
        """
        category_df = self.df[self.df['category'] == category]
        return category_df['manufacturer'].dropna().unique().tolist()

    def get_models_by_manufacturer(self, category: str, manufacturer: str):
        """
        Получает список всех уникальных моделей по категории и производителю,
        исключая модели, у которых stock <= 0.

        :param category: Категория товара (например, 'СМАРТФОНЫ')
        :param manufacturer: Производитель (например, 'Apple')
        :return: Список уникальных моделей в наличии
        """
        category_df = self.df[self.df['category'] == category]
        manufacturer_df = category_df[category_df['manufacturer'] == manufacturer]

        # Фильтруем товары с ненулевым количеством stock
        available_models_df = manufacturer_df[manufacturer_df["stock"] > 0]

        return available_models_df['short_name'].dropna().unique().tolist()

    def get_product_configuration(self, model_name):
        """
        Возвращает конфигурацию (цвет, память) для конкретного short_name,
        но только те варианты, у которых stock > 0.
        """
        model_info = self.df[self.df['short_name'] == model_name]
        colors = model_info["color"].unique().tolist()
        product_configuration = {}

        for color in colors:
            product_color_info = model_info[model_info["color"] == color]
            # Словарь для памяти (разных вариантов) внутри одного цвета.
            memory_dict = {}

            for row in product_color_info.itertuples(index=False):
                # row.stock — остаток. Если он не заполнен, стоит ещё проверить, что нет None.
                if row.stock and row.stock > 0:
                    memory_dict[row.memory] = {
                        "id": row.id,
                        "category": row.category,
                        "manufacturer": row.manufacturer,
                        "name": row.name,
                        "photo": row.photo,
                        "description": row.description,
                        "price": row.price,
                        "stock": row.stock,
                    }

            # Если по данному цвету хотя бы один вариант памяти не пустой — добавляем.
            if memory_dict:
                product_configuration[color] = memory_dict

        return product_configuration

    def get_product_by_id(self, product_id: int):
        """
        Получает все данные по ID товара.

        :param product_id: ID товара
        :return: Список значений (без заголовков)
        """
        product_info = self.df[self.df['id'] == product_id]
        if product_info.empty:
            return None  # Если товар не найден, возвращаем None

        return product_info.iloc[0].to_dict()  # Возвращаем все значения первой найденной строки


db = ProductDatabase()
# print(db.get_product_by_id(44))
