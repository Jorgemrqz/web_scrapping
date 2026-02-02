<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { Chart } from 'chart.js/auto';
import { marked } from 'marked';
import DataExplorer from './DataExplorer.vue';

const props = defineProps({
    dashboardData: Object,
    activeTab: String,
    topic: String
});

const globalChartInstance = ref(null);
const engagementChartInstance = ref(null);
const platformChartInstance = ref(null);
const radarChartInstance = ref(null);

// Computed Metrics
const metricPos = computed(() => {
    if (!props.dashboardData) return '0%';
    const total = getTotal();
    if (total === 0) return '0%';
    return Math.round((props.dashboardData.stats.global_counts['Positivo'] || 0) / total * 100) + '%';
});

const metricNeu = computed(() => {
    if (!props.dashboardData) return '0%';
    const total = getTotal();
    if (total === 0) return '0%';
    return Math.round((props.dashboardData.stats.global_counts['Neutro'] || 0) / total * 100) + '%';
});

const metricNeg = computed(() => {
    if (!props.dashboardData) return '0%';
    const total = getTotal();
    if (total === 0) return '0%';
    return Math.round((props.dashboardData.stats.global_counts['Negativo'] || 0) / total * 100) + '%';
});

const metricTotal = computed(() => getTotal());

const quickInsight = computed(() => {
    if (!props.dashboardData) return 'Generando resumen...';
    const counts = props.dashboardData.stats.global_counts;
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
    if (!props.dashboardData || !props.dashboardData.storytelling) return '<p>Generando narrativa...</p>';
    return marked.parse(props.dashboardData.storytelling);
});

function getTotal() {
    if (!props.dashboardData) return 0;
    const counts = props.dashboardData.stats.global_counts;
    return (counts['Positivo'] || 0) + (counts['Neutro'] || 0) + (counts['Negativo'] || 0);
}

function getPlatformLabel(p) {
    return p.toLowerCase() === 'twitter' ? 'X' : p.charAt(0).toUpperCase() + p.slice(1);
}

// Charts Logic
function renderCharts() {
    if (!props.dashboardData) return;
    
    const stats = props.dashboardData.stats;
    const platforms = Object.keys(stats.by_platform);
    
    // --- 1. Global Chart (Doughnut) ---
    const ctxGlobal = document.getElementById('globalChart');
    if (ctxGlobal) {
        if (globalChartInstance.value) globalChartInstance.value.destroy();
        const counts = stats.global_counts;
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
                plugins: { legend: { position: 'bottom', labels: { color: '#cbd5e1', font: {family: 'Outfit'} } } },
                layout: { padding: 10 }
            }
        });
    }

    // --- 2. Engagement Chart (Pie - Volume per platform) ---
    const ctxEngagement = document.getElementById('engagementChart');
    if (ctxEngagement) {
        if (engagementChartInstance.value) engagementChartInstance.value.destroy();
        
        // Calculate total posts per platform
        const platformVolumes = platforms.map(p => {
            const c = stats.by_platform[p];
            return (c['Positivo']||0) + (c['Neutro']||0) + (c['Negativo']||0);
        });

        engagementChartInstance.value = new Chart(ctxEngagement, {
            type: 'pie',
            data: {
                labels: platforms.map(getPlatformLabel),
                datasets: [{
                    data: platformVolumes,
                    backgroundColor: ['#3b82f6', '#8b5cf6', '#f59e0b', '#ec4899', '#10b981'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { color: '#cbd5e1' } } }
            }
        });
    }

    // --- 3. Platform Stacked Bar Chart ---
    const ctxPlatform = document.getElementById('platformChart');
    if (ctxPlatform) {
        if (platformChartInstance.value) platformChartInstance.value.destroy();
        
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
                labels: platforms.map(getPlatformLabel),
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true, ticks: { color: '#94a3b8' }, grid: { display: false } },
                    y: { stacked: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                },
                plugins: { legend: { labels: { color: '#cbd5e1' } } }
            }
        });
    }

    // --- 4. Radar Chart (Sentiment Intensity Analysis) ---
    const ctxRadar = document.getElementById('radarChart');
    if (ctxRadar) {
        if (radarChartInstance.value) radarChartInstance.value.destroy();
        
        // Calculate % Positive and % Negative per platform
        const posRates = [];
        const negRates = [];
        
        platforms.forEach(p => {
            const c = stats.by_platform[p];
            const total = (c['Positivo']||0) + (c['Neutro']||0) + (c['Negativo']||0);
            if (total > 0) {
                posRates.push(((c['Positivo']||0) / total * 100).toFixed(1));
                negRates.push(((c['Negativo']||0) / total * 100).toFixed(1));
            } else {
                posRates.push(0);
                negRates.push(0);
            }
        });

        radarChartInstance.value = new Chart(ctxRadar, {
            type: 'radar',
            data: {
                labels: platforms.map(getPlatformLabel),
                datasets: [
                    {
                        label: '% Positividad',
                        data: posRates,
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        borderColor: '#10b981',
                        pointBackgroundColor: '#10b981'
                    },
                    {
                        label: '% Negatividad',
                        data: negRates,
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        borderColor: '#ef4444',
                        pointBackgroundColor: '#ef4444'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        angleLines: { color: 'rgba(255,255,255,0.1)' },
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        pointLabels: { color: '#cbd5e1', font: { size: 12 } },
                        ticks: { backdropColor: 'transparent', color: '#94a3b8' }
                    }
                },
                plugins: { legend: { labels: { color: '#cbd5e1' } } }
            }
        });
    }
}

// Lifecycle
onMounted(() => {
    // Initial render
    renderCharts();
});

// Watch triggers
watch(() => props.dashboardData, () => {
    nextTick(renderCharts);
}, { deep: true });

watch(() => props.activeTab, (newTab) => {
    if (newTab === 'overview' || newTab === 'platforms') {
        setTimeout(() => {
            nextTick(renderCharts);
        }, 100);
    }
});

defineExpose({
    resizeCharts: () => {
        if (globalChartInstance.value) globalChartInstance.value.resize();
        if (engagementChartInstance.value) engagementChartInstance.value.resize();
        if (platformChartInstance.value) platformChartInstance.value.resize();
        if (radarChartInstance.value) radarChartInstance.value.resize();
    }
});
</script>

<template>
    <div class="view-container">
        
        <header class="mobile-header">
            <h3>Resultados: <span class="highlight">{{ topic }}</span></h3>
        </header>

        <!-- TAB: OVERVIEW -->
        <div v-show="activeTab === 'overview'" class="tab-content active">
            <!-- KPIs -->
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
                    <div class="icon-box total"><i class="fa-solid fa-database"></i></div>
                    <div class="metric-info">
                        <h3>Muestra</h3>
                        <p>{{ metricTotal }}</p>
                    </div>
                </div>
            </div>

            <!-- Charts Row (Dual) -->
            <div class="charts-grid-2">
                <div class="chart-card glass-card">
                    <div class="card-header">
                        <h3><i class="fa-solid fa-chart-donut"></i> Sentimiento Global</h3>
                    </div>
                    <div class="chart-wrapper">
                        <canvas id="globalChart"></canvas>
                    </div>
                </div>
                <div class="chart-card glass-card">
                     <div class="card-header">
                        <h3><i class="fa-solid fa-chart-pie"></i> Volumen por Plataforma</h3>
                    </div>
                    <div class="chart-wrapper">
                         <canvas id="engagementChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Insights (Full Width) -->
            <div class="glass-card" style="margin-top: 24px;">
                 <div class="card-header">
                    <h3><i class="fa-solid fa-lightbulb"></i> Insights IA</h3>
                </div>
                <div class="quick-insights" v-html="quickInsight"></div>
            </div>
        </div>

        <!-- TAB: PLATFORMS -->
        <div v-show="activeTab === 'platforms'" class="tab-content active">
            <div class="section-header" style="margin-bottom: 20px;">
                <h2>Análisis Comparativo</h2>
                <p style="color: var(--text-secondary);">Métricas detalladas por canal.</p>
            </div>
            
            <div class="charts-grid-2">
                <!-- Stacked Bar -->
                <div class="chart-card glass-card">
                    <div class="card-header">
                        <h3><i class="fa-solid fa-chart-column"></i> Volumen y Sentimiento</h3>
                    </div>
                    <div class="chart-wrapper">
                        <canvas id="platformChart"></canvas>
                    </div>
                </div>

                <!-- Radar Map -->
                <div class="chart-card glass-card">
                    <div class="card-header">
                        <h3><i class="fa-solid fa-crosshairs"></i> Intensidad de Sentimiento (%)</h3>
                    </div>
                    <div class="chart-wrapper">
                        <canvas id="radarChart"></canvas>
                    </div>
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
            <DataExplorer :dashboardData="dashboardData" />
        </div>

    </div>
</template>

<style scoped>
.charts-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
}

@media (max-width: 1024px) {
    .charts-grid-2 {
        grid-template-columns: 1fr;
    }
}
</style>
