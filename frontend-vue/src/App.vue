<script setup>
import { ref, onMounted, computed, nextTick } from 'vue';
import Sidebar from './components/Sidebar.vue';
import SearchView from './components/SearchView.vue';
import Dashboard from './components/Dashboard.vue';

// --- Estado Reactivo ---
// Vistas
const currentView = ref('search'); // 'search' | 'dashboard'
const activeTab = ref('overview'); // 'overview' | 'platforms' | 'storytelling' | 'data'
const isSidebarCollapsed = ref(false);

// Datos de Búsqueda
const topic = ref('');
const limit = ref(10);
const isLoading = ref(false);
const isScraping = ref(false);
const scrapingTopic = ref('');
const statusText = ref('Listo para conectar con redes sociales.');
const statusColor = ref('text-secondary'); 

// Datos del Dashboard
const dashboardData = ref(null);
const searchHistory = ref([]);
const API_URL = 'http://127.0.0.1:8000';

const dashboardRef = ref(null); // Reference to Dashboard component

// --- Computed ---
const hasData = computed(() => !!dashboardData.value);

// --- Métodos ---

function toggleSidebar() {
    isSidebarCollapsed.value = !isSidebarCollapsed.value;
    // Resize charts in Dashboard component
    setTimeout(() => {
        if (dashboardRef.value) {
            dashboardRef.value.resizeCharts();
        }
    }, 350);
}

async function startAnalysis() {
    if (!topic.value.trim()) {
        statusText.value = "⚠️ Por favor ingresa un tema.";
        statusColor.value = "text-danger"; 
        return;
    }

    isLoading.value = true;
    isScraping.value = true;
    scrapingTopic.value = topic.value;
    localStorage.setItem('activeScrapeTopic', topic.value);
    statusText.value = "🚀 Iniciando agentes de scraping...";
    statusColor.value = "text-secondary";

    try {
        const response = await fetch(`${API_URL}/scrape`, { 
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
            // USAR scrapingTopic, no topic, para evitar conflictos si el usuario cambia de vista
            if (!scrapingTopic.value) return; 

            // Verificar Status primero (más robusto)
            const statusRes = await fetch(`${API_URL}/status/${encodeURIComponent(scrapingTopic.value)}`);
            if (statusRes.ok) {
                const statusData = await statusRes.json();
                if (statusData.cancelled) {
                     clearInterval(interval);
                     statusText.value = "⛔ Análisis cancelado.";
                     isScraping.value = false;
                     isLoading.value = false;
                     localStorage.removeItem('activeScrapeTopic');
                     return;
                }
            }

            // Verificar Resultados
            const res = await fetch(`${API_URL}/results/${encodeURIComponent(scrapingTopic.value)}`);
            if (res.status === 200) {
                const data = await res.json();
                clearInterval(interval);
                
                statusText.value = "✅ ¡Análisis Completado!";
                isScraping.value = false;
                localStorage.removeItem('activeScrapeTopic');
                
                // Solo cargar dashboard automáticamente si el usuario no cambió de tema
                if (topic.value === scrapingTopic.value) {
                    setTimeout(() => {
                        loadDashboard(data);
                        fetchHistory(); 
                    }, 500);
                } else {
                     // Notificar o actualizar historial silenciosamente
                     fetchHistory();
                     alert(`¡El análisis de "${scrapingTopic.value}" ha terminado!`);
                }

            } else if (res.status !== 404) {
                 if (res.status >= 500) {
                     console.warn(`Server Error ${res.status}. Retrying polling...`);
                 } else {
                    clearInterval(interval);
                    statusText.value = "❌ Error Fatal en el análisis.";
                    isLoading.value = false;
                    isScraping.value = false;
                    localStorage.removeItem('activeScrapeTopic');
                 }
            }
        } catch (e) {
            console.log("Polling error", e);
        }
    }, 3000);
}

function loadDashboard(data) {
    console.log("✅ LIVE: Dashboard loaded.");
    
    // Inject expanded state for comments (handled in DataExplorer now, but ensuring data integrity)
    if (data.data_preview) {
        data.data_preview.forEach(row => {
            row.commentPage = 1; 
        });
    }

    dashboardData.value = data;
    isLoading.value = false;
    currentView.value = 'dashboard';
    statusText.value = "Listo para nueva búsqueda.";
    
    // Charts execution handled by Dashboard component watchers
}

async function loadHistoryItem(itemTopic) {
    topic.value = itemTopic;
    dashboardData.value = null; 
    isLoading.value = true;
    currentView.value = 'search'; 
    statusText.value = "Cargando análisis previo...";
    
    try {
        const res = await fetch(`${API_URL}/results/${itemTopic}`);
        if (res.ok) {
            const data = await res.json();
            loadDashboard(data);
        } else {
            statusText.value = "Error cargando historial.";
            isLoading.value = false;
        }
    } catch (e) {
        isLoading.value = false;
        console.error(e);
    }
}

function resetSearch() {
    if (isScraping.value) {
        // Volver al Progreso
        topic.value = scrapingTopic.value;
        dashboardData.value = null;
        currentView.value = 'search';
        isLoading.value = true;
        return;
    }
    // Nueva búsqueda
    dashboardData.value = null;
    currentView.value = 'search';
    topic.value = '';
    isSidebarCollapsed.value = false; 
}

function switchTab(tab) {
    if (!hasData.value) return; 
    activeTab.value = tab;
    // Charts resize handled by Dashboard component watcher on activeTab
}

async function fetchHistory() {
    try {
        const res = await fetch(`${API_URL}/history`);
        if (res.ok) {
            searchHistory.value = await res.json();
        }
    } catch (e) {
        console.error("Error cargando historial", e);
    }
}

onMounted(async () => {
    fetchHistory();
    fetchHistory();
    
    // Recuperar sesión de scraping si existe
    const savedTopic = localStorage.getItem('activeScrapeTopic');
    if (savedTopic) {
        console.log("Restaurando sesión de scraping para:", savedTopic);
        topic.value = savedTopic;
        scrapingTopic.value = savedTopic;
        isScraping.value = true;
        isLoading.value = true; // Mostrar tracker
        statusText.value = "🔄 Reconectando con proceso activo...";
        pollResults(); // Reiniciar polling
    }

    try {
        const response = await fetch(`${API_URL}/`);
        if (response.ok) {
            statusText.value = "Conexión exitosa con el servidor.";
        } else {
            statusText.value = "Conectado, pero el servidor respondió error.";
        }
    } catch (e) {
        statusText.value = "Servidor no detectado. Asegúrate de ejecutar el backend con 'python api.py'";
    }
});
async function deleteHistoryItem(itemTopic) {
    if (!confirm(`¿Estás seguro de que quieres eliminar el historial de "${itemTopic}"?`)) return;
    
    try {
        const res = await fetch(`${API_URL}/history/${itemTopic}`, { method: 'DELETE' });
        if (res.ok) {
            // Remove from local state immediately or re-fetch
            searchHistory.value = searchHistory.value.filter(i => i.topic !== itemTopic);
            // Also if current viewed dashboard is this topic, reset?
            if (topic.value === itemTopic && currentView.value === 'dashboard') {
                resetSearch();
            }
        } else {
            alert("Error eliminando historial.");
        }
    } catch (e) {
        console.error("Error deleting history", e);
    }
}
</script>

<template>
  <!-- Background -->
  <div class="glass-background"></div>

  <div class="app-container">
    
    <!-- SIDEBAR -->
    <Sidebar 
        :isSidebarCollapsed="isSidebarCollapsed"
        :activeTab="activeTab"
        :currentView="currentView"
        :searchHistory="searchHistory"
        :hasData="hasData"
        :isLoading="isScraping"
        @toggle-sidebar="toggleSidebar"
        @reset-search="resetSearch"
        @switch-tab="switchTab"
        @load-history-item="loadHistoryItem"
        @fetch-history="fetchHistory"
        @delete-history-item="deleteHistoryItem"
    />

    <!-- MAIN CONTENT -->
    <main class="main-content">
        
        <!-- SEARCH VIEW -->
        <SearchView 
            v-if="currentView === 'search'"
            v-model:topic="topic"
            v-model:limit="limit"
            :isLoading="isLoading"
            :statusText="statusText"
            :statusColor="statusColor"
            @start-analysis="startAnalysis"
        />

        <!-- DASHBOARD VIEW -->
        <Dashboard 
            v-else
            ref="dashboardRef"
            :dashboardData="dashboardData"
            :activeTab="activeTab"
            :topic="topic"
        />
        
    </main>
  </div>
</template>

<style scoped>
/* Main app styles are in style.css */
</style>
