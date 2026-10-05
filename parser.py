import os
import re
import requests
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import logging

logger = logging.getLogger(__name__)

class GiftSiteParser:
    GIFT_KEYWORDS = [
        'подарок', 'подарки', 'gift', 'gifts', 'набор', 'наборы',
        'новогодн', 'новый год', 'каталог', 'catalog', 'корпоратив',
        'коробка', 'коробки', 'box', 'упаковка', 'сувенир', 'сладости', 'конфеты'
    ]

    EXCLUDE_DOCS = [
        'политика', 'privacy', 'оферта', 'соглашение', 'договор',
        'реквизиты', 'инн', 'огрн', 'устав', 'вакансии', 'возврат'
    ]

    CATALOG_EXTS = ['.pdf', '.xlsx', '.xls']
    IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp']

    def __init__(self, download_dir: str = 'static/downloads'):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.download_dir = download_dir
        self.visited_urls = set()
        self.found_catalogs = []
        self.found_images = []

    def parse_site(self, base_url: str, task_id: str) -> dict:
        self.visited_urls.clear()
        self.found_catalogs.clear()
        self.found_images.clear()

        pages_to_scan = [base_url]
        try:
            res = self.session.get(base_url, timeout=10, headers={'User-Agent': self.ua.random})
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'lxml')
                base_domain = urlparse(base_url).netloc
                for a in soup.find_all('a', href=True):
                    href = urljoin(base_url, a['href']).split('#')[0]
                    if urlparse(href).netloc == base_domain and href not in pages_to_scan:
                        txt = (a.get_text() + " " + href).lower()
                        if any(k in txt for k in ['catalog', 'каталог', 'podar', 'подар', 'nabor', 'product']):
                            pages_to_scan.append(href)
                            if len(pages_to_scan) >= 15:
                                break
        except Exception as e:
            logger.warning(f"Crawl error: {e}")

        for page in pages_to_scan[:15]:
            self._extract_from_page(page)

        return {
            'catalogs': self._dedup(self.found_catalogs, 'url'),
            'images': self._dedup(self.found_images, 'url'),
            'pages_scanned': len(self.visited_urls),
            'site_url': base_url
        }

    def _extract_from_page(self, page_url: str):
        if page_url in self.visited_urls:
            return
        self.visited_urls.add(page_url)
        try:
            res = self.session.get(page_url, timeout=10, headers={'User-Agent': self.ua.random})
            if res.status_code != 200 or 'text/html' not in res.headers.get('content-type', ''):
                return
            soup = BeautifulSoup(res.text, 'lxml')

            # PDF / Excel
            for a in soup.find_all('a', href=True):
                href = urljoin(page_url, a['href'])
                ext = os.path.splitext(urlparse(href).path)[1].lower()
                if ext in self.CATALOG_EXTS:
                    txt = (a.get_text() + " " + href).lower()
                    if not any(ex in txt for ex in self.EXCLUDE_DOCS):
                        self.found_catalogs.append({
                            'url': href,
                            'name': a.get_text().strip() or os.path.basename(href),
                            'type': ext.replace('.', ''),
                            'source_page': page_url
                        })

            # Изображения
            for img in soup.find_all('img', src=True):
                src = urljoin(page_url, img['src'])
                ext = os.path.splitext(urlparse(src).path)[1].lower()
                if ext in self.IMAGE_EXTS:
                    alt = img.get('alt', '')
                    txt = (alt + " " + src).lower()
                    if not any(bad in txt for bad in ['logo', 'icon', 'favicon', 'arrow', 'banner', 'avatar', 'payment']):
                        self.found_images.append({
                            'url': src,
                            'alt': alt or 'Подарочный набор',
                            'source_page': page_url
                        })
        except Exception as e:
            logger.warning(f"Error reading page {page_url}: {e}")

    @staticmethod
    def _dedup(items, key):
        seen = set()
        res = []
        for i in items:
            if i[key] not in seen:
                seen.add(i[key])
                res.append(i)
        return res
