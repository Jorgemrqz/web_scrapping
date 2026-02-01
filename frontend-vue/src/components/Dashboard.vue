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
const platformChartInstance = ref(null);

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

// Charts Logic
function renderCharts() {
    if (!props.dashboardData) return;
    
    // Global Chart
    const ctxGlobal = document.getElementById('globalChart');
    if (ctxGlobal) {
        if (globalChartInstance.value) globalChartInstance.value.destroy();
        
        const counts = props.dashboardData.stats.global_counts;
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
        
        const stats = props.dashboardData.stats;
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

// Lifecycle
onMounted(() => {
    // Initial render
    renderCharts();
});

// Watch for data changes or tab switches to re-render charts
watch(() => props.dashboardData, () => {
    nextTick(renderCharts);
}, { deep: true });

watch(() => props.activeTab, (newTab) => {
    if (newTab === 'overview' || newTab === 'platforms') {
        setTimeout(() => {
            nextTick(renderCharts);
        }, 50);
    }
});

// Expose resize method for parent to call
defineExpose({
    resizeCharts: () => {
        if (globalChartInstance.value) globalChartInstance.value.resize();
        if (platformChartInstance.value) platformChartInstance.value.resize();
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
            <DataExplorer :dashboardData="dashboardData" />
        </div>

    </div>
</template>
