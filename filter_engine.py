class GiftFilter:
    def filter_catalogs(self, catalogs: list) -> list:
        # Каталоги уже отфильтрованы парсером от юридического мусора
        return catalogs

    def filter_images(self, images: list) -> list:
        # Ограничиваем выдачу лучшими 40 фото
        return images[:40]
