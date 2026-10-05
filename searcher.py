import requests
import re
import time
from urllib.parse import urlparse, quote_plus
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompanySiteSearcher:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.exclude_domains = {
            'youtube.com', 'facebook.com', 'instagram.com', 'vk.com',
            'twitter.com', 'wikipedia.org', 'linkedin.com', 'tiktok.com',
            'avito.ru', 'hh.ru', 'wildberries.ru', 'ozon.ru',
            'market.yandex.ru', 'zoon.ru', 'yell.ru', '2gis.ru',
            'flamp.ru', 'irecommend.ru', 'otzovik.com', 'cataloxy.ru',
            'rusprofile.ru', 'sbis.ru', 'list-org.com', 'google.com',
            'yandex.ru', 'bing.com', 'mail.ru'
        }

    def search_duckduckgo(self, company_name: str) -> list:
        results = []
        query = quote_plus(f'{company_name} официальный сайт новогодние подарки каталог')
        try:
            url = f'https://html.duckduckgo.com/html/?q={query}'
            headers = {'User-Agent': self.ua.random}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'lxml')
            for link in soup.find_all('a', class_='result__a'):
                href = link.get('href', '')
                if href.startswith('http'):
                    domain = urlparse(href).netloc.replace('www.', '')
                    if domain not in self.exclude_domains:
                        results.append({'url': href, 'domain': domain, 'source': 'duckduckgo'})
        except Exception as e:
            logger.warning(f"DDG search error: {e}")
        return results

    def try_direct_url(self, company_name: str) -> list:
        results = []
        clean = self._transliterate(company_name.lower().strip())
        clean = re.sub(r'[^a-z0-9]', '', clean)
        domains = [f'https://{clean}.ru', f'https://www.{clean}.ru', f'https://{clean}.com']
        for url in domains:
            try:
                res = requests.get(url, timeout=5, headers={'User-Agent': self.ua.random})
                if res.status_code == 200:
                    dom = urlparse(res.url).netloc.replace('www.', '')
                    results.append({'url': res.url, 'domain': dom, 'source': 'direct'})
            except Exception:
                continue
        return results

    def find_company_site(self, company_name: str) -> dict:
        all_results = []
        all_results.extend(self.search_duckduckgo(company_name))
        all_results.extend(self.try_direct_url(company_name))

        if not all_results:
            # Запасной вариант - пробуем просто имя.ru
            clean = self._transliterate(company_name.lower().strip())
            clean = re.sub(r'[^a-z0-9]', '', clean)
            return {'success': True, 'url': f'https://{clean}.ru', 'domain': f'{clean}.ru', 'all_candidates': []}

        best = all_results[0]
        return {
            'success': True,
            'url': best['url'],
            'domain': best['domain'],
            'all_candidates': all_results[:5]
        }

    @staticmethod
    def _transliterate(text: str) -> str:
        t = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
            'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
            'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
            'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': ''
        }
        return ''.join(t.get(c, c) for c in text)
