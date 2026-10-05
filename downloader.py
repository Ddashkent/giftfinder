import os
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
