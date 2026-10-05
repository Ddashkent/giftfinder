import os
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
