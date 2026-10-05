import os

# Структура папок
os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("static/downloads", exist_ok=True)

files = {}

files["requirements.txt"] = """Flask==3.0.0
gunicorn==21.2.0
requests==2.31.0
beautifulsoup4==4.12.2
lxml==4.9.3
Pillow
fake-useragent==1.4.0
PyPDF2==3.0.1
openpyxl==3.1.2
"""

files[".gitignore"] = """venv/
__pycache__/
*.pyc
static/downloads/*
!static/downloads/.gitkeep
"""

files["static/downloads/.gitkeep"] = ""

files["searcher.py"] = '''import requests
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
'''

files["parser.py"] = '''import os
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
'''

files["filter_engine.py"] = '''class GiftFilter:
    def filter_catalogs(self, catalogs: list) -> list:
        # Каталоги уже отфильтрованы парсером от юридического мусора
        return catalogs

    def filter_images(self, images: list) -> list:
        # Ограничиваем выдачу лучшими 40 фото
        return images[:40]
'''

files["downloader.py"] = '''import os
import requests
import hashlib
from urllib.parse import urlparse

class FileDownloader:
    def __init__(self, base_dir: str = 'static/downloads'):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def download_file(self, url: str, task_id: str, file_type: str = 'catalogs') -> dict:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, timeout=20, stream=True, headers=headers)
            if res.status_code != 200:
                return {'success': False}

            task_folder = os.path.join(self.base_dir, task_id, file_type)
            os.makedirs(task_folder, exist_ok=True)

            url_hash = hashlib.md5(url.encode()).hexdigest()[:6]
            path_name = os.path.basename(urlparse(url).path) or f"file_{url_hash}"
            filename = f"{url_hash}_{path_name}"
            
            full_path = os.path.join(task_folder, filename)
            with open(full_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)

            size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2)
            rel_path = f"downloads/{task_id}/{file_type}/{filename}"

            return {
                'success': True,
                'filename': filename,
                'local_path': full_path,
                'relative_path': rel_path,
                'size_mb': size_mb
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
'''

files["app.py"] = '''import os
import uuid
import threading
import zipfile
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file
from searcher import CompanySiteSearcher
from parser import GiftSiteParser
from filter_engine import GiftFilter
from downloader import FileDownloader

app = Flask(__name__)
tasks = {}

searcher = CompanySiteSearcher()
gift_filter = GiftFilter()
downloader = FileDownloader('static/downloads')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.json or {}
    company_name = data.get('company_name', '').strip()
    if not company_name:
        return jsonify({'error': 'Введите название компании'}), 400

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        'id': task_id,
        'company_name': company_name,
        'status': 'searching',
        'progress': 15,
        'message': f'Ищем официальный сайт «{company_name}»...'
    }

    threading.Thread(target=_worker_search, args=(task_id, company_name), daemon=True).start()
    return jsonify({'task_id': task_id})

@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    if task_id not in tasks:
        return jsonify({'error': 'Задача не найдена'}), 404
    return jsonify(tasks[task_id])

@app.route('/api/download-all/<task_id>')
def api_download_all(task_id):
    task_dir = os.path.join('static/downloads', task_id)
    if not os.path.exists(task_dir):
        return jsonify({'error': 'Файлы не найдены'}), 404

    mem = BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files_list in os.walk(task_dir):
            for file in files_list:
                fp = os.path.join(root, file)
                zf.write(fp, os.path.relpath(fp, task_dir))
    mem.seek(0)
    company = tasks.get(task_id, {}).get('company_name', 'gifts')
    return send_file(mem, mimetype='application/zip', as_attachment=True, download_name=f'{company}_podarki.zip')

def _worker_search(task_id, company_name):
    task = tasks[task_id]
    try:
        sr = searcher.find_company_site(company_name)
        if not sr.get('success'):
            task['status'] = 'error'
            task['message'] = 'Сайт не найден. Попробуйте уточнить название.'
            return

        site_url = sr['url']
        task['site_url'] = site_url
        task['progress'] = 40
        task['message'] = f'Сайт найден: {sr.get("domain")}. Сканируем подарки и каталоги...'

        parser = GiftSiteParser('static/downloads')
        parsed = parser.parse_site(site_url, task_id)

        task['progress'] = 75
        task['message'] = 'Скачиваем найденные каталоги и фото...'

        cats = gift_filter.filter_catalogs(parsed['catalogs'])
        imgs = gift_filter.filter_images(parsed['images'])

        for c in cats:
            res = downloader.download_file(c['url'], task_id, 'catalogs')
            if res.get('success'):
                c['local_path'] = res['relative_path']
                c['size_mb'] = res['size_mb']

        for im in imgs:
            res = downloader.download_file(im['url'], task_id, 'images')
            if res.get('success'):
                im['local_path'] = res['relative_path']

        task['status'] = 'completed'
        task['progress'] = 100
        task['message'] = 'Готово!'
        task['results'] = {
            'catalogs': cats,
            'images': imgs,
            'pages_scanned': parsed['pages_scanned'],
            'site_url': site_url
        }
    except Exception as e:
        task['status'] = 'error'
        task['message'] = f'Ошибка: {str(e)}'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''

files["templates/index.html"] = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎁 Поиск новогодних подарков и каталогов</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
</head>
<body>
    <header class="header">
        <div class="container">
            <div class="logo"><i class="fas fa-gift"></i> <span>GiftFinder</span></div>
            <p class="subtitle">Сервис поиска новогодних подарков, каталогов и прайсов поставщиков</p>
        </div>
    </header>

    <main class="container main">
        <div class="card search-card">
            <h2><i class="fas fa-search"></i> Поиск поставщика</h2>
            <p class="hint">Введите бренд, фабрику или название компании (например: <b>Конфаэль</b>, <b>Амадей</b>, <b>Красный Октябрь</b>):</p>
            <div class="search-box">
                <input type="text" id="companyInput" placeholder="Название компании..." autocomplete="off">
                <button id="searchBtn" onclick="startSearch()"><i class="fas fa-search"></i> Найти подарки</button>
            </div>
        </div>

        <div id="progressBlock" class="card progress-card" style="display: none;">
            <h3 id="progressTitle"><i class="fas fa-spinner fa-spin"></i> Обработка...</h3>
            <div class="bar-wrap"><div id="progressBar" class="bar"></div></div>
            <p id="progressMsg">Ищем сайт...</p>
        </div>

        <div id="resultsBlock" style="display: none;">
            <div class="stats-grid">
                <div class="stat-card">
                    <i class="fas fa-file-pdf"></i>
                    <div><b id="countCats">0</b><span>Каталогов</span></div>
                </div>
                <div class="stat-card">
                    <i class="fas fa-images"></i>
                    <div><b id="countImgs">0</b><span>Фотографий</span></div>
                </div>
                <div class="stat-card action">
                    <button class="btn-zip" onclick="downloadZip()"><i class="fas fa-download"></i> Скачать всё (ZIP)</button>
                </div>
            </div>

            <div class="card section-block">
                <h3><i class="fas fa-file-pdf"></i> Найденные каталоги и прайсы</h3>
                <div id="catalogsList" class="cats-list"></div>
            </div>

            <div class="card section-block">
                <h3><i class="fas fa-boxes-stacked"></i> Фотографии подарков и наборов</h3>
                <div id="imagesList" class="imgs-grid"></div>
            </div>
        </div>
    </main>
    <script src="/static/js/main.js"></script>
</body>
</html>
'''

files["static/css/style.css"] = '''* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', sans-serif; background: #f4f6f9; color: #2c3e50; }
.container { max-width: 1000px; margin: 0 auto; padding: 0 15px; }
.header { background: linear-gradient(135deg, #e74c3c, #c0392b); color: #fff; padding: 30px 0; text-align: center; }
.logo { font-size: 28px; font-weight: 700; margin-bottom: 5px; }
.subtitle { font-size: 14px; opacity: 0.9; }
.main { padding: 30px 15px; }
.card { background: #fff; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 20px; }
.search-card h2 { margin-bottom: 8px; color: #e74c3c; font-size: 20px; }
.hint { font-size: 14px; color: #7f8c8d; margin-bottom: 15px; }
.search-box { display: flex; gap: 10px; }
.search-box input { flex: 1; padding: 14px 18px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 16px; outline: none; }
.search-box input:focus { border-color: #e74c3c; }
.search-box button { background: #e74c3c; color: #fff; border: none; padding: 0 25px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 15px; }
.search-box button:hover { background: #c0392b; }
.bar-wrap { height: 18px; background: #eee; border-radius: 10px; overflow: hidden; margin: 15px 0; }
.bar { height: 100%; width: 0; background: linear-gradient(90deg, #e74c3c, #f39c12); transition: width 0.4s; }
.stats-grid { display: grid; grid-template-columns: 1fr 1fr 1.5fr; gap: 15px; margin-bottom: 20px; }
.stat-card { background: #fff; border-radius: 12px; padding: 18px; display: flex; align-items: center; gap: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.04); }
.stat-card i { font-size: 30px; color: #e74c3c; }
.stat-card b { font-size: 24px; display: block; }
.stat-card span { font-size: 13px; color: #7f8c8d; }
.btn-zip { width: 100%; height: 100%; min-height: 50px; background: #27ae60; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
.btn-zip:hover { background: #219653; }
.cats-list { display: flex; flex-direction: column; gap: 10px; margin-top: 15px; }
.cat-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
.cat-item a { color: #e74c3c; text-decoration: none; font-weight: 600; }
.imgs-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; margin-top: 15px; }
.img-card { border-radius: 8px; overflow: hidden; background: #f8fafc; border: 1px solid #e2e8f0; }
.img-card img { width: 100%; height: 160px; object-fit: cover; display: block; }
.img-card p { padding: 8px; font-size: 12px; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
'''

files["static/js/main.js"] = '''let currentTaskId = null;
let pollTimer = null;

function startSearch() {
    const val = document.getElementById('companyInput').value.trim();
    if (!val) return alert('Введите название!');

    document.getElementById('searchBtn').disabled = true;
    document.getElementById('resultsBlock').style.display = 'none';
    document.getElementById('progressBlock').style.display = 'block';

    fetch('/api/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ company_name: val })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) throw new Error(data.error);
        currentTaskId = data.task_id;
        pollTimer = setInterval(checkStatus, 1500);
    })
    .catch(err => {
        alert(err.message);
        document.getElementById('searchBtn').disabled = false;
        document.getElementById('progressBlock').style.display = 'none';
    });
}

function checkStatus() {
    fetch('/api/task/' + currentTaskId)
    .then(r => r.json())
    .then(task => {
        document.getElementById('progressBar').style.width = task.progress + '%';
        document.getElementById('progressMsg').innerText = task.message || '';

        if (task.status === 'completed') {
            clearInterval(pollTimer);
            document.getElementById('searchBtn').disabled = false;
            document.getElementById('progressBlock').style.display = 'none';
            showResults(task.results);
        } else if (task.status === 'error') {
            clearInterval(pollTimer);
            alert(task.message);
            document.getElementById('searchBtn').disabled = false;
            document.getElementById('progressBlock').style.display = 'none';
        }
    });
}

function showResults(res) {
    document.getElementById('resultsBlock').style.display = 'block';
    document.getElementById('countCats').innerText = (res.catalogs || []).length;
    document.getElementById('countImgs').innerText = (res.images || []).length;

    const catsList = document.getElementById('catalogsList');
    if (!res.catalogs || res.catalogs.length === 0) {
        catsList.innerHTML = '<p style="color:#94a3b8">Каталоги не найдены на сайте</p>';
    } else {
        catsList.innerHTML = res.catalogs.map(c => `
            <div class="cat-item">
                <span>📄 <b>${c.name}</b> (${c.type.toUpperCase()})</span>
                <a href="${c.local_path ? '/static/' + c.local_path : c.url}" target="_blank" download>Скачать</a>
            </div>
        `).join('');
    }

    const imgsList = document.getElementById('imagesList');
    if (!res.images || res.images.length === 0) {
        imgsList.innerHTML = '<p style="color:#94a3b8">Фотографии не найдены</p>';
    } else {
        imgsList.innerHTML = res.images.map(img => `
            <div class="img-card">
                <img src="${img.local_path ? '/static/' + img.local_path : img.url}" loading="lazy" onerror="this.src='https://placehold.co/200x200?text=Gift'">
                <p>${img.alt || 'Подарок'}</p>
            </div>
        `).join('');
    }
}

function downloadZip() {
    if (currentTaskId) {
        window.open('/api/download-all/' + currentTaskId, '_blank');
    }
}

document.getElementById('companyInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startSearch();
});
'''

# Запись всех файлов
for path, content in files.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print(" Все 8 файлов успешно созданы в папке gifts!")
