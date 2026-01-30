const API_URL = ""; // Relative path since served by same backend

let globalChartInstance = null;
let platformChartInstance = null;
let pollingInterval = null;

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

    // Reset UI
    document.getElementById('dashboard').classList.add('hidden');
    statusText.style.color = "#94a3b8";
    btn.disabled = true;
    btnText.style.display = 'none';
    loader.style.display = 'block';

    try {
        // 1. Start Scrape Task
        statusText.textContent = "🚀 Iniciando agentes de scraping...";

        const response = await fetch(`${API_URL}/scrape`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic: topic, limit: parseInt(limit) })
        });

        if (!response.ok) throw new Error("Error starting scrape");

        // 2. Poll for results
        statusText.textContent = "⏳ Extrayendo datos y analizando con IA... (Esto puede tomar unos minutos)";

        if (pollingInterval) clearInterval(pollingInterval);

        pollingInterval = setInterval(async () => {
            await checkResults(topic);
        }, 3000); // Check every 3 seconds

    } catch (error) {
        console.error(error);
        statusText.textContent = "❌ Error al conectar con el servidor.";
        resetButton();
    }
}

async function checkResults(topic) {
    try {
        const res = await fetch(`${API_URL}/results/${encodeURIComponent(topic)}`);
        if (res.status === 200) {
            const data = await res.json();
            clearInterval(pollingInterval);
            renderDashboard(data);
            resetButton();
            document.getElementById('statusText').textContent = "✅ ¡Análisis Completado!";
            document.getElementById('statusText').style.color = "#10b981";
        } else if (res.status === 404) {
            // Still processing
        } else {
            // Error
            clearInterval(pollingInterval);
            resetButton();
        }
    } catch (e) {
        console.log("Polling error", e);
    }
}

function resetButton() {
    const btn = document.getElementById('analyzeBtn');
    const loader = document.getElementById('btnLoader');
    const btnText = btn.querySelector('.btn-text');
    btn.disabled = false;
    btnText.style.display = 'block';
    loader.style.display = 'none';
}

function renderDashboard(data) {
    document.getElementById('dashboard').classList.remove('hidden');

    // 1. Storytelling
    document.getElementById('storyContent').innerHTML = marked.parse(data.storytelling || "No story generated.");

    // 2. Charts
    renderCharts(data.stats);

    // 3. Table
    renderTable(data.data_preview);
}

function renderCharts(stats) {
    const ctxGlobal = document.getElementById('globalChart').getContext('2d');
    const ctxPlatform = document.getElementById('platformChart').getContext('2d');

    // Destroy previous
    if (globalChartInstance) globalChartInstance.destroy();
    if (platformChartInstance) platformChartInstance.destroy();

    // colors
    const colors = {
        'Positivo': '#10b981',
        'Neutro': '#94a3b8',
        'Negativo': '#ef4444'
    };

    // Data Prep Global
    const labels = Object.keys(stats.global_counts);
    const values = Object.values(stats.global_counts);
    const bgColors = labels.map(l => colors[l] || '#cbd5e1');

    globalChartInstance = new Chart(ctxGlobal, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: bgColors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: 'white' } }
            }
        }
    });

    // Data Prep Platform (Stacked Bar)
    const platforms = Object.keys(stats.by_platform);
    const sentiments = ['Positivo', 'Neutro', 'Negativo']; // Fixed order

    const datasets = sentiments.map(sent => ({
        label: sent,
        data: platforms.map(p => stats.by_platform[p][sent] || 0),
        backgroundColor: colors[sent]
    }));

    platformChartInstance = new Chart(ctxPlatform, {
        type: 'bar',
        data: {
            labels: platforms.map(p => p.toUpperCase()),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { stacked: true, ticks: { color: 'white' } },
                y: { stacked: true, ticks: { color: 'white' } }
            },
            plugins: {
                legend: { labels: { color: 'white' } }
            }
        }
    });
}

function renderTable(rows) {
    const tbody = document.querySelector('#dataTable tbody');
    tbody.innerHTML = '';

    rows.forEach(row => {
        const sentiment = row.sentiment_llm || 'N/A';
        let sentimentClass = '';
        if (sentiment.includes('Positivo')) sentimentClass = 'tag-pos';
        else if (sentiment.includes('Negativo')) sentimentClass = 'tag-neg';
        else sentimentClass = 'tag-neu';

        // Truncate content
        let content = row.post_content || '';
        if (content.length > 80) content = content.substring(0, 80) + '...';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.platform || '-'}</td>
            <td class="${sentimentClass}">${sentiment}</td>
            <td>${content}</td>
        `;
        tbody.appendChild(tr);
    });
}
