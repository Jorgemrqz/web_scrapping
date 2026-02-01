<script setup>
import { ref } from 'vue';

const props = defineProps({
    isSidebarCollapsed: Boolean,
    activeTab: String,
    currentView: String,
    searchHistory: Array,
    hasData: Boolean
});

const emit = defineEmits([
    'toggle-sidebar',
    'reset-search',
    'switch-tab',
    'load-history-item',
    'fetch-history',
    'delete-history-item'
]);

const isHistoryOpen = ref(true); // Default open or closed? User request implies "desplegable", let's default to false or true. Let's start true to show off, or false to be clean. User said "cuando le de salga un sub menu", implying click to open. So start false? No, user said "que el historial estuviera dentro... y que cuando le de salga...". 
// Let's rely on user interaction. Default false.
// Actually, I'll initialize it to false.

function toggleHistory() {
    if (props.isSidebarCollapsed) {
        emit('toggle-sidebar'); // Expand if collapsed
        isHistoryOpen.value = true;
    } else {
        isHistoryOpen.value = !isHistoryOpen.value;
    }
}

function loadHistoryItem(topic) {
    emit('load-history-item', topic);
}

</script>

<template>
    <nav class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
        <!-- Sidebar Toggle -->
        <div class="sidebar-toggle" @click="$emit('toggle-sidebar')">
             <i :class="isSidebarCollapsed ? 'fa-solid fa-chevron-right' : 'fa-solid fa-chevron-left'"></i>
        </div>

        <div class="logo-area">
            <i class="fa-solid fa-bolt pulse-icon-fa"></i>
            <h2>Sentiment<span class="highlight">Pulse</span></h2>
        </div>
        
        <ul class="nav-links">
            <li :class="{ active: activeTab === 'overview', 'disabled-link': !hasData }" @click="hasData && $emit('switch-tab', 'overview')" title="Visión Global">
                <i class="fa-solid fa-chart-pie"></i> <span>Visión Global</span>
            </li>
            <li :class="{ active: activeTab === 'platforms', 'disabled-link': !hasData }" @click="hasData && $emit('switch-tab', 'platforms')" title="Plataformas">
                <i class="fa-brands fa-hubspot"></i> <span>Por Plataforma</span>
            </li>
            <li :class="{ active: activeTab === 'storytelling', 'disabled-link': !hasData }" @click="hasData && $emit('switch-tab', 'storytelling')" title="Storytelling">
                <i class="fa-solid fa-book-open-reader"></i> <span>Storytelling AI</span>
            </li>
            <li :class="{ active: activeTab === 'data', 'disabled-link': !hasData }" @click="hasData && $emit('switch-tab', 'data')" title="Datos">
                <i class="fa-solid fa-table-list"></i> <span>Explorador de Datos</span>
            </li>

            <div class="divider" style="margin: 15px 0; border-top: 1px solid rgba(255,255,255,0.05);"></div>

            <!-- History Dropdown -->
            <li @click="toggleHistory" :class="{ 'active-history': isHistoryOpen && !isSidebarCollapsed }" class="history-main-item">
                <div class="history-label">
                     <i class="fa-solid fa-clock-rotate-left"></i> <span>Historial de Búsquedas</span>
                </div>
                <i v-if="!isSidebarCollapsed" class="fa-solid fa-chevron-down chevron" :class="{ rotated: isHistoryOpen }"></i>
            </li>
            
            <!-- Submenu -->
            <transition name="slide-fade">
                <ul v-if="isHistoryOpen && !isSidebarCollapsed" class="submenu">
                    <li v-if="searchHistory.length === 0" class="submenu-empty">
                        No hay historial reciente.
                    </li>
                    <li v-for="(item, idx) in searchHistory" :key="idx" class="submenu-item" @click.stop="loadHistoryItem(item.topic)">
                        <div class="history-content">
                             <span class="topic-name">{{ item.topic }}</span>
                             <span class="comment-count" v-if="item.total_comments">
                                <i class="fa-regular fa-comment-dots"></i> {{ item.total_comments }}
                             </span>
                        </div>
                        <i class="fa-solid fa-xmark delete-icon" @click.stop="$emit('delete-history-item', item.topic)" title="Borrar"></i>
                    </li>
                </ul>
            </transition>
        </ul>

        <!-- Spacer to push footer down -->
        <div style="flex: 1;"></div>

        <div class="nav-footer">
            <button class="new-search-btn" @click="$emit('reset-search')" title="Nueva Búsqueda">
                <i class="fa-solid fa-magnifying-glass"></i> <span v-if="!isSidebarCollapsed">Nueva Búsqueda</span>
            </button>
        </div>

    </nav>
</template>

<style scoped>
.history-main-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.history-label {
    display: flex;
    align-items: center;
    gap: 12px;
}

.chevron {
    font-size: 0.8em;
    transition: transform 0.3s ease;
    opacity: 0.7;
}

.chevron.rotated {
    transform: rotate(180deg);
}

.submenu {
    list-style: none;
    margin-top: 5px;
    margin-left: 10px;
    padding-left: 10px;
    border-left: 1px solid rgba(255,255,255,0.1);
}

.submenu-item {
    padding: 8px 12px;
    font-size: 0.9em;
    color: var(--text-secondary);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
}

.history-content {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    flex: 1;
}

.topic-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 500;
}

.comment-count {
    font-size: 0.75em;
    opacity: 0.6;
    display: flex;
    align-items: center;
    gap: 4px;
}

.delete-icon {
    opacity: 0;
    font-size: 0.8em;
    padding: 4px;
    border-radius: 50%;
    transition: all 0.2s;
    color: var(--text-secondary);
}

.submenu-item:hover .delete-icon {
    opacity: 1;
}

.delete-icon:hover {
    background: rgba(239, 68, 68, 0.2);
    color: var(--danger);
}

.submenu-item:hover {
    background: rgba(255,255,255,0.05);
    color: var(--text-primary);
    transform: translateX(3px);
}

.submenu-empty {
    padding: 10px;
    font-size: 0.85em;
    color: rgba(255,255,255,0.3);
    font-style: italic;
}

/* Transition for submenu */
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
  max-height: 300px;
  opacity: 1;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  max-height: 0;
  opacity: 0;
  margin-top: 0;
}
</style>
