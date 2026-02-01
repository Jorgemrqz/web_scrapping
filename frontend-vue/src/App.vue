<script setup>
import { ref, onMounted, computed, nextTick } from 'vue';
import { Chart } from 'chart.js/auto';
import { marked } from 'marked';

// --- Estado Reactivo ---
// Vistas
const currentView = ref('search'); // 'search' | 'dashboard'
const activeTab = ref('overview'); // 'overview' | 'platforms' | 'storytelling' | 'data'
const isSidebarCollapsed = ref(false);

// Datos de Búsqueda
const topic = ref('');
const limit = ref(10);
const isLoading = ref(false);
const statusText = ref('Listo para conectar con redes sociales.');
const statusColor = ref('text-secondary'); // clase CSS para color

// Datos del Dashboard
const dashboardData = ref(null);
const globalChartInstance = ref(null);
const platformChartInstance = ref(null);

// Filtros de Tabla
const platformFilter = ref('all');
const sentimentFilter = ref('all');

// --- Computed ---
const metricPos = computed(() => {
    if (!dashboardData.value) return '0%';
    const total = getTotal();
    if (total === 0) return '0%';
    return Math.round((dashboardData.value.stats.global_counts['Positivo'] || 0) / total * 100) + '%';
});

const metricNeu = computed(() => {
    if (!dashboardData.value) return '0%';
    const total = getTotal();
    if (total === 0) return '0%';
    return Math.round((dashboardData.value.stats.global_counts['Neutro'] || 0) / total * 100) + '%';
});

const metricNeg = computed(() => {
    if (!dashboardData.value) return '0%';
    const total = getTotal();
    if (total === 0) return '0%';
    return Math.round((dashboardData.value.stats.global_counts['Negativo'] || 0) / total * 100) + '%';
});

const metricTotal = computed(() => getTotal());

const filteredData = computed(() => {
    if (!dashboardData.value) return [];
    
    return dashboardData.value.data_preview.filter(row => {
        const matchPlatform = platformFilter.value === 'all' || row.platform.toLowerCase() === platformFilter.value.toLowerCase();
        const matchSentiment = sentimentFilter.value === 'all' || (row.sentiment_llm && row.sentiment_llm.includes(sentimentFilter.value));
        return matchPlatform && matchSentiment;
    });
});

const quickInsight = computed(() => {
    if (!dashboardData.value) return 'Generando resumen...';
    const counts = dashboardData.value.stats.global_counts;
    const pos = counts['Positivo'] || 0;
    const neg = counts['Negativo'] || 0;
    
    if (pos > neg * 1.5) {
        return "La percepción es fuertemente <strong>positiva</strong>. Los usuarios están recibiendo bien este tema.";
    } else if (neg > pos * 1.5) {
        return "Hay una tendencia <strong>negativa</strong> considerable. Se detectan puntos de fricción o críticas.";
    } else {
        return "La opinión está <strong>dividida</strong>. No hay un consenso claro entre los usuarios.";
    }
});

const storytellingHtml = computed(() => {
    if (!dashboardData.value || !dashboardData.value.storytelling) return '<p>Generando narrativa...</p>';
    return marked.parse(dashboardData.value.storytelling);
});

// --- Métodos ---

function toggleSidebar() {
    isSidebarCollapsed.value = !isSidebarCollapsed.value;
    // Resize charts after transition (300ms matches CSS transition)
    setTimeout(() => {
        if (globalChartInstance.value) globalChartInstance.value.resize();
        if (platformChartInstance.value) platformChartInstance.value.resize();
    }, 350);
}

function getTotal() {
    if (!dashboardData.value) return 0;
    const counts = dashboardData.value.stats.global_counts;
    return (counts['Positivo'] || 0) + (counts['Neutro'] || 0) + (counts['Negativo'] || 0);
}

async function startAnalysis() {
    if (!topic.value.trim()) {
        statusText.value = "⚠️ Por favor ingresa un tema.";
        statusColor.value = "text-danger"; // Fixed: use css variable or known class
        return;
    }

    isLoading.value = true;
    statusText.value = "🚀 Iniciando agentes de scraping...";
    statusColor.value = "text-secondary";

    try {
        const response = await fetch('/scrape', { 
             method: 'POST',
             headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({ topic: topic.value, limit: parseInt(limit.value) })
        });

        if (!response.ok) throw new Error("Error starting scrape");

        statusText.value = "⏳ Analizando millones de puntos de datos con IA...";
        
        pollResults();

    } catch (error) {
        console.error(error);
        statusText.value = "❌ Error al conectar con el servidor.";
        isLoading.value = false;
    }
}

function pollResults() {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/results/${encodeURIComponent(topic.value)}`);
            if (res.status === 200) {
                const data = await res.json();
                clearInterval(interval);
                
                statusText.value = "✅ ¡Análisis Completado!";
                setTimeout(() => {
                    loadDashboard(data);
                }, 500);
            } else if (res.status !== 404) {
                clearInterval(interval);
                statusText.value = "❌ Error en el análisis.";
                isLoading.value = false;
            }
        } catch (e) {
            console.log("Polling error", e);
        }
    }, 3000);
}

function loadDashboard(data) {
    dashboardData.value = data;
    isLoading.value = false;
    currentView.value = 'dashboard';
    statusText.value = "Listo para nueva búsqueda.";
    
    // Render Charts after DOM update and transition
    setTimeout(() => {
        nextTick(() => {
            renderCharts();
        });
    }, 100);
}

function resetSearch() {
    dashboardData.value = null;
    currentView.value = 'search';
    topic.value = '';
    isSidebarCollapsed.value = false; // Reset sidebar
}

const hasData = computed(() => !!dashboardData.value);

function switchTab(tab) {
    if (!hasData.value) return; 
    activeTab.value = tab;
    if (tab === 'overview' || tab === 'platforms') {
        setTimeout(() => {
            nextTick(() => {
                renderCharts();
            });
        }, 50);
    }
}

// Exponer funciones al template si no se usa <script setup> (pero estamos usando <script setup>)
// En <script setup>, las funciones top-level ya están expuestas.
// El error '_ctx.getIcon is not a function' sugiere que Vue pierde el contexto en ciertos bloques o es un problema de hot-reload.
// Asegurémonos de que son funciones normales.

// --- Helper Functions ---
function renderCharts() {
    if (!dashboardData.value) return;
    
    // Global Chart
    const ctxGlobal = document.getElementById('globalChart');
    if (ctxGlobal) {
        if (globalChartInstance.value) globalChartInstance.value.destroy();
        
        const counts = dashboardData.value.stats.global_counts;
        globalChartInstance.value = new Chart(ctxGlobal, {
            type: 'doughnut',
            data: {
                labels: ['Positivo', 'Neutro', 'Negativo'],
                datasets: [{
                    data: [counts['Positivo']||0, counts['Neutro']||0, counts['Negativo']||0],
                    backgroundColor: ['#10b981', '#94a3b8', '#ef4444'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { color: '#cbd5e1', font: {family: 'Outfit'} } }
                },
                layout: { padding: 20 }
            }
        });
    }

    // Platform Chart
    const ctxPlatform = document.getElementById('platformChart');
    if (ctxPlatform) {
        if (platformChartInstance.value) platformChartInstance.value.destroy();
        
        const stats = dashboardData.value.stats;
        const platforms = Object.keys(stats.by_platform);
        const colors = { 'Positivo': '#10b981', 'Neutro': '#94a3b8', 'Negativo': '#ef4444' };
        
        const datasets = ['Positivo', 'Neutro', 'Negativo'].map(sent => ({
            label: sent,
            data: platforms.map(p => stats.by_platform[p][sent] || 0),
            backgroundColor: colors[sent],
            borderRadius: 4
        }));

        platformChartInstance.value = new Chart(ctxPlatform, {
            type: 'bar',
            data: {
                labels: platforms.map(p => p.charAt(0).toUpperCase() + p.slice(1)), 
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
}

const getIcon = (platform) => {
    if (!platform) return 'link';
    const p = platform.toLowerCase();
    if (p.includes('twitter') || p.includes('x')) return 'twitter';
    if (p.includes('facebook')) return 'facebook';
    if (p.includes('linkedin')) return 'linkedin';
    if (p.includes('instagram')) return 'instagram';
    if (p.includes('reddit')) return 'reddit';
    return 'hashtag';
};

const getSentimentClass = (text) => {
    if (!text) return 'tag-neu';
    if (text.includes('Positivo')) return 'tag-pos';
    if (text.includes('Negativo')) return 'tag-neg';
    return 'tag-neu';
};
</script>

<template>
  <!-- Background -->
  <div class="glass-background"></div>

  <div class="app-container">
    
    <!-- SIDEBAR (Always Visibe) -->
    <nav class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
        <!-- Sidebar Toggle -->
        <div class="sidebar-toggle" @click="toggleSidebar">
             <i :class="isSidebarCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-left'"></i>
        </div>

        <div class="logo-area">
            <i class="fa-solid fa-bolt pulse-icon-fa"></i>
            <h2>Sentiment<span class="highlight">Pulse</span></h2>
        </div>
        
        <ul class="nav-links">
            <li :class="{ active: activeTab === 'overview', 'disabled-link': !hasData }" @click="hasData && switchTab('overview')" title="Visión Global">
                <i class="fa-solid fa-chart-pie"></i> <span>Visión Global</span>
            </li>
            <li :class="{ active: activeTab === 'platforms', 'disabled-link': !hasData }" @click="hasData && switchTab('platforms')" title="Plataformas">
                <i class="fa-brands fa-hubspot"></i> <span>Por Plataforma</span>
            </li>
            <li :class="{ active: activeTab === 'storytelling', 'disabled-link': !hasData }" @click="hasData && switchTab('storytelling')" title="Storytelling">
                <i class="fa-solid fa-book-open-reader"></i> <span>Storytelling AI</span>
            </li>
            <li :class="{ active: activeTab === 'data', 'disabled-link': !hasData }" @click="hasData && switchTab('data')" title="Datos">
                <i class="fa-solid fa-table-list"></i> <span>Explorador de Datos</span>
            </li>
        </ul>

        <div class="nav-footer">
            <button class="new-search-btn" @click="resetSearch" title="Nueva Búsqueda">
                <i class="fa-solid fa-magnifying-glass"></i> <span v-if="!isSidebarCollapsed">Nueva Búsqueda</span>
            </button>
        </div>
    </nav>

    <!-- MAIN CONTENT -->
    <main class="main-content">
        
        <!-- SEARCH VIEW (WELCOME PAGE) -->
        <div v-if="currentView === 'search'" class="view-container active-view">
            <div class="search-hero">
                <div class="hero-text">
                    <h1>Bienvenido a <br>Social Sentiment <span class="highlight">Pulse</span></h1>
                    <p>Empieza a analizar la opinión pública en tiempo real.</p>
                </div>

                <div class="search-card glass-card">
                    <div class="input-wrapper">
                        <i class="fa-solid fa-magnifying-glass search-icon"></i>
                        <input type="text" v-model="topic" placeholder="Escribe un tema (ej: Elecciones, iPhone 16...)" autocomplete="off" @keyup.enter="startAnalysis">
                    </div>
                    
                    <div class="options-wrapper">
                        <label><i class="fa-solid fa-filter"></i> Límite de Post por red:</label>
                        <input type="number" v-model="limit" min="5" max="50">
                    </div>

                    <button id="analyzeBtn" @click="startAnalysis" :disabled="isLoading">
                        <span v-if="!isLoading" class="btn-text">Iniciar Análisis Inteligente</span>
                        <div v-else class="loader"></div>
                    </button>
                    
                    <p class="status-message" :class="statusColor">{{ statusText }}</p>
                </div>

                <!-- FEATURES GRID (NEW) -->
                <div class="features-grid">
                    <div class="feature-item">
                        <div class="feature-icon"><i class="fa-solid fa-robot"></i></div>
                        <h3>IA Avanzada</h3>
                        <p>Análisis de sentimiento potenciado por LLMs locales.</p>
                    </div>
                    <div class="feature-item">
                        <div class="feature-icon"><i class="fa-solid fa-network-wired"></i></div>
                        <h3>Multi-Plataforma</h3>
                        <p>Scraping simultáneo de Twitter, LinkedIn y más.</p>
                    </div>
                    <div class="feature-item">
                        <div class="feature-icon"><i class="fa-solid fa-chart-line"></i></div>
                        <h3>Insights Reales</h3>
                        <p>Descubre tendencias ocultas en los comentarios.</p>
                    </div>
                </div>

            </div>
        </div>

        <!-- DASHBOARD VIEW -->
        <div v-else class="view-container">
            
            <header class="mobile-header">
                <h3>Resultados: <span class="highlight">{{ topic }}</span></h3>
            </header>

            <!-- TAB: OVERVIEW -->
            <div v-show="activeTab === 'overview'" class="tab-content active">
                <div class="metrics-row">
                    <div class="metric-card glass-card">
                        <div class="icon-box pos"><i class="fa-solid fa-face-smile"></i></div>
                        <div class="metric-info">
                            <h3>Positivo</h3>
                            <p>{{ metricPos }}</p>
                        </div>
                    </div>
                    <div class="metric-card glass-card">
                        <div class="icon-box neu"><i class="fa-solid fa-face-meh"></i></div>
                        <div class="metric-info">
                            <h3>Neutro</h3>
                            <p>{{ metricNeu }}</p>
                        </div>
                    </div>
                    <div class="metric-card glass-card">
                        <div class="icon-box neg"><i class="fa-solid fa-face-frown"></i></div>
                        <div class="metric-info">
                            <h3>Negativo</h3>
                            <p>{{ metricNeg }}</p>
                        </div>
                    </div>
                    <div class="metric-card glass-card">
                        <div class="icon-box total"><i class="fa-solid fa-comments"></i></div>
                        <div class="metric-info">
                            <h3>Total</h3>
                            <p>{{ metricTotal }}</p>
                        </div>
                    </div>
                </div>

                <div class="charts-row">
                    <div class="chart-card glass-card big-chart">
                        <div class="card-header">
                            <h3><i class="fa-solid fa-chart-donut"></i> Distribución Global de Sentimiento</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="globalChart"></canvas>
                        </div>
                    </div>
                    <div class="chart-card glass-card small-chart">
                         <div class="card-header">
                            <h3><i class="fa-solid fa-lightbulb"></i> Insights Rápidos</h3>
                        </div>
                        <div class="quick-insights" v-html="quickInsight"></div>
                    </div>
                </div>
            </div>

            <!-- TAB: PLATFORMS -->
            <div v-show="activeTab === 'platforms'" class="tab-content active">
                <div class="section-header" style="margin-bottom: 20px;">
                    <h2>Análisis por Plataforma</h2>
                    <p style="color: var(--text-secondary);">Comparativa de sentimiento entre redes sociales.</p>
                </div>
                <div class="chart-card glass-card full-width">
                    <div class="chart-wrapper">
                        <canvas id="platformChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- TAB: STORYTELLING -->
            <div v-show="activeTab === 'storytelling'" class="tab-content active">
                <div class="story-container glass-card">
                    <div class="story-header">
                        <i class="fa-solid fa-robot"></i>
                        <div>
                            <h2>Informe Narrativo AI</h2>
                            <p>Interpretación contextual de los datos.</p>
                        </div>
                    </div>
                    <div class="markdown-body" v-html="storytellingHtml"></div>
                </div>
            </div>

            <!-- TAB: DATA -->
            <div v-show="activeTab === 'data'" class="tab-content active">
                <div class="data-controls glass-card">
                    <div class="filter-group">
                        <label>Filtrar por Red:</label>
                        <select v-if="dashboardData" v-model="platformFilter">
                            <option value="all">Todas</option>
                            <option v-for="p in Object.keys(dashboardData.stats.by_platform)" :key="p" :value="p">
                                {{ p.charAt(0).toUpperCase() + p.slice(1) }}
                            </option>
                        </select>
                    </div>
                    <div class="filter-group">
                         <label>Sentimiento:</label>
                        <select v-model="sentimentFilter">
                            <option value="all">Todos</option>
                            <option value="Positivo">Positivo</option>
                            <option value="Neutro">Neutro</option>
                            <option value="Negativo">Negativo</option>
                        </select>
                    </div>
                </div>

                <div class="table-container glass-card">
                    <table>
                        <thead>
                            <tr>
                                <th>Red / Autor</th>
                                <th>Contenido</th>
                                <th>Sentimiento</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template v-for="(post, idx) in filteredData" :key="idx">
                                <!-- Post Row -->
                                <tr class="post-row">
                                    <td style="width: 200px;">
                                        <div style="display: flex; flex-direction: column; gap: 4px;">
                                            <span><i :class="`fa-brands fa-${getIcon(post.platform)}`"></i> <strong>{{ post.platform }}</strong></span>
                                            <span style="font-size: 0.8em; opacity: 0.7;">{{ post.author || 'Anónimo' }}</span>
                                        </div>
                                    </td>
                                    <td>
                                        <div style="font-weight: 500; margin-bottom: 5px;">{{ post.content }}</div>
                                        <div v-if="post.comments && post.comments.length" style="font-size: 0.85em; opacity: 0.8;">
                                            <i class="fa-solid fa-comments"></i> {{ post.comments.length }} comentarios
                                        </div>
                                    </td>
                                    <td>
                                        <span :class="getSentimentClass(post.sentiment_llm)">{{ post.sentiment_llm || 'Neutro' }}</span>
                                    </td>
                                </tr>
                                <!-- Comments Rows (Nested) -->
                                <tr v-for="(comment, cIdx) in post.comments" :key="`${idx}-c-${cIdx}`" class="comment-row">
                                    <td style="padding-left: 30px; border-bottom: 1px dashed var(--glass-border);">
                                        <i class="fa-solid fa-reply" style="transform: rotate(180deg); margin-right: 5px; opacity: 0.5;"></i> 
                                        {{ comment.author || 'Usuario' }}
                                    </td>
                                    <td style="border-bottom: 1px dashed var(--glass-border); color: #cbd5e1;">
                                        {{ comment.content }}
                                    </td>
                                    <td style="border-bottom: 1px dashed var(--glass-border);">
                                        <span :class="getSentimentClass(comment.sentiment)" style="opacity: 0.8; font-size: 0.85em;">{{ comment.sentiment || 'Neutro' }}</span>
                                    </td>
                                </tr>
                            </template>

                            <tr v-if="filteredData.length === 0">
                                <td colspan="3" style="text-align: center; padding: 20px;">No hay datos para mostrar con estos filtros.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    </main>
  </div>
</template>

<style scoped>
/* Scoped styles specific to components if needed, 
   but we are using global styles.css for the main theme. */
</style>
