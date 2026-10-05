let currentTaskId = null;
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
