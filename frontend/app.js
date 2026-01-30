const API_URL = "";
let globalChartInstance = null;
let platformChartInstance = null;
let pollingInterval = null;
let currentData = null; // Store full data for filtering

// === MAIN ACTIONS ===

async function startAnalysis() {
    const topic = document.getElementById('topicInput').value.trim();
    const limit = document.getElementById('limitInput').value;
    const btn = document.getElementById('analyzeBtn');
    const loader = document.getElementById('btnLoader');
    const statusText = document.getElementById('statusText');
    const btnText = btn.querySelector('.btn-text');

    if (!topic) {
        statusText.textContent = "⚠️ Por favor ingresa un tema.";
        statusText.style.color = "#ef4444";
        return;
    }

    // UI Loading State
    statusText.style.color = "#94a3b8";
    btn.disabled = true;
    btnText.style.display = 'none';
    loader.classList.remove('hidden');

    try {
        statusText.textContent = "🚀 Iniciando agentes de scraping...";

        const response = await fetch(`${API_URL}/scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic: topic, limit: parseInt(limit) })
        });

        if (!response.ok) throw new Error("Error starting scrape");

        statusText.textContent = "⏳ Analizando millones de puntos de datos con IA...";

        if (pollingInterval) clearInterval(pollingInterval);

        // Start Polling
        pollingInterval = setInterval(async () => {
            await checkResults(topic);
        }, 3000);

    } catch (error) {
        console.error(error);
        statusText.textContent = "❌ Error al conectar con el servidor.";
        resetButtonState();
    }
}

async function checkResults(topic) {
    try {
        const res = await fetch(`${API_URL}/results/${encodeURIComponent(topic)}`);
        if (res.status === 200) {
            const data = await res.json();
            clearInterval(pollingInterval);

            // Success!
            document.getElementById('statusText').textContent = "✅ ¡Análisis Completado!";
            setTimeout(() => {
                loadDashboard(topic, data);
            }, 500);

        } else if (res.status === 404) {
            // Still processing...
        } else {
            clearInterval(pollingInterval);
            document.getElementById('statusText').textContent = "❌ Error en el análisis.";
            resetButtonState();
        }
    } catch (e) {
        console.log("Polling error", e);
    }
}

function loadDashboard(topic, data) {
    currentData = data; // Store data
    resetButtonState();

    // 1. Switch Views
    document.getElementById('searchView').classList.add('hidden');
    document.getElementById('searchView').classList.remove('active-view');

    document.getElementById('dashboardView').classList.remove('hidden');
    document.getElementById('sidebar').classList.remove('hidden');

    document.getElementById('currentTopic').textContent = topic;

    // 2. Populate Metrics
    const counts = data.stats.global_counts;
    const total = (counts['Positivo'] || 0) + (counts['Neutro'] || 0) + (counts['Negativo'] || 0);

    // Animate numbers (simple visual)
    document.getElementById('metric-total').textContent = total;
    document.getElementById('metric-pos').textContent = total ? Math.round((counts['Positivo'] || 0) / total * 100) + '%' : '0%';
    document.getElementById('metric-neu').textContent = total ? Math.round((counts['Neutro'] || 0) / total * 100) + '%' : '0%';
    document.getElementById('metric-neg').textContent = total ? Math.round((counts['Negativo'] || 0) / total * 100) + '%' : '0%';

    // 3. Quick Insights (Simple generation)
    generateQuickInsights(counts);

    // 4. Charts
    renderCharts(data.stats);

    // 5. Storytelling
    document.getElementById('storyContent').innerHTML = marked.parse(data.storytelling || "Generando narrativa...");

    // 6. Table & Filters
    populatePlatformFilter(data.stats.by_platform);
    renderTable(data.data_preview);

    // Default Tab
    switchTab('overview');
}

function resetButtonState() {
    const btn = document.getElementById('analyzeBtn');
    const loader = document.getElementById('btnLoader');
    const btnText = btn.querySelector('.btn-text');

    btn.disabled = false;
    btnText.style.display = 'block';
    loader.classList.add('hidden');
}

function resetSearch() {
    document.getElementById('dashboardView').classList.add('hidden');
    document.getElementById('sidebar').classList.add('hidden');

    document.getElementById('searchView').classList.remove('hidden');
    document.getElementById('searchView').classList.add('active-view');

    document.getElementById('statusText').textContent = "Listo para nueva búsqueda.";
    document.getElementById('topicInput').value = "";
}

// === TABS & NAVIGATION ===

function switchTab(tabId) {
    // 1. Sidebar Active State
    const navLinks = document.querySelectorAll('.nav-links li');
    navLinks.forEach(li => li.classList.remove('active'));

    // Find the link that calls this function (approximate match)
    const activeLink = Array.from(navLinks).find(li => li.getAttribute('onclick').includes(tabId));
    if (activeLink) activeLink.classList.add('active');

    // 2. Tab Content Visibility
    const contents = document.querySelectorAll('.tab-content');
    contents.forEach(c => c.classList.remove('active'));

    document.getElementById(`tab-${tabId}`).classList.add('active');
}

// === VISUALIZATION ===

function generateQuickInsights(counts) {
    const pos = counts['Positivo'] || 0;
    const neg = counts['Negativo'] || 0;
    let text = "";

    if (pos > neg * 1.5) {
        text = "La percepción es fuertemente <strong>positiva</strong>. Los usuarios están recibiendo bien este tema.";
    } else if (neg > pos * 1.5) {
        text = "Hay una tendencia <strong>negativa</strong> considerable. Se detectan puntos de fricción o críticas.";
    } else {
        text = "La opinión está <strong>dividida</strong>. No hay un consenso claro entre los usuarios.";
    }

    document.getElementById('quickInsights').innerHTML = `<p>${text}</p>`;
}

function renderCharts(stats) {
    const ctxGlobal = document.getElementById('globalChart').getContext('2d');
    const ctxPlatform = document.getElementById('platformChart').getContext('2d');

    if (globalChartInstance) globalChartInstance.destroy();
    if (platformChartInstance) platformChartInstance.destroy();

    const colors = {
        'Positivo': '#10b981',
        'Neutro': '#94a3b8',
        'Negativo': '#ef4444'
    };

    // Global Doughnut
    globalChartInstance = new Chart(ctxGlobal, {
        type: 'doughnut',
        data: {
            labels: ['Positivo', 'Neutro', 'Negativo'],
            datasets: [{
                data: [stats.global_counts['Positivo'] || 0, stats.global_counts['Neutro'] || 0, stats.global_counts['Negativo'] || 0],
                backgroundColor: [colors.Positivo, colors.Neutro, colors.Negativo],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { color: '#cbd5e1', padding: 20, font: { family: 'Outfit' } } }
            },
            layout: { padding: 20 }
        }
    });

    // Platform Stacked Bar
    const platforms = Object.keys(stats.by_platform);
    const datasets = ['Positivo', 'Neutro', 'Negativo'].map(sent => ({
        label: sent,
        data: platforms.map(p => stats.by_platform[p][sent] || 0),
        backgroundColor: colors[sent],
        borderRadius: 4
    }));

    platformChartInstance = new Chart(ctxPlatform, {
        type: 'bar',
        data: {
            labels: platforms.map(p => p.charAt(0).toUpperCase() + p.slice(1)), // Capitalize
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { stacked: true, ticks: { color: '#94a3b8' }, grid: { display: false } },
                y: { stacked: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            },
            plugins: {
                legend: { labels: { color: '#cbd5e1' } }
            }
        }
    });
}

// === DATA TABLE ===

function populatePlatformFilter(byPlatform) {
    const select = document.getElementById('platformFilter');
    select.innerHTML = '<option value="all">Todas</option>';

    Object.keys(byPlatform).forEach(p => {
        const option = document.createElement('option');
        option.value = p;
        option.textContent = p.charAt(0).toUpperCase() + p.slice(1);
        select.appendChild(option);
    });
}

function filterTable() {
    if (!currentData) return;

    const platform = document.getElementById('platformFilter').value;
    const sentiment = document.getElementById('sentimentFilter').value;

    const filtered = currentData.data_preview.filter(row => {
        const matchPlatform = platform === 'all' || row.platform.toLowerCase() === platform.toLowerCase();
        const matchSentiment = sentiment === 'all' || (row.sentiment_llm && row.sentiment_llm.includes(sentiment));
        return matchPlatform && matchSentiment;
    });

    renderTable(filtered);
}

function renderTable(rows) {
    const tbody = document.querySelector('#dataTable tbody');
    tbody.innerHTML = '';

    rows.forEach(row => {
        const tr = document.createElement('tr');

        // Sentiment Tag
        let sentClass = 'tag-neu';
        let sentText = row.sentiment_llm || 'Neutro';
        if (sentText.includes('Positivo')) sentClass = 'tag-pos';
        else if (sentText.includes('Negativo')) sentClass = 'tag-neg';

        tr.innerHTML = `
            <td><i class="fa-brands fa-${getIcon(row.platform)}"></i> ${row.platform}</td>
            <td><span class="${sentClass}">${sentText}</span></td>
            <td>${row.post_content ? row.post_content.substring(0, 100) + '...' : ''}</td>
        `;
        tbody.appendChild(tr);
    });
}

function getIcon(platform) {
    if (!platform) return 'link';
    const p = platform.toLowerCase();
    if (p.includes('twitter') || p.includes('x')) return 'twitter';
    if (p.includes('facebook')) return 'facebook';
    if (p.includes('linkedin')) return 'linkedin';
    if (p.includes('instagram')) return 'instagram';
    if (p.includes('reddit')) return 'reddit';
    return 'hashtag';
}
