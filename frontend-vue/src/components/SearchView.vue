<script setup>
import { defineAsyncComponent } from 'vue';
import ProgressTracker from './ProgressTracker.vue';

defineProps({
    topic: String,
    limit: Number,
    isLoading: Boolean,
    statusText: String,
    statusColor: String
});

const emit = defineEmits(['update:topic', 'update:limit', 'start-analysis']);

function startAnalysis() {
    emit('start-analysis');
}
</script>

<template>
    <div class="view-container active-view">
        <div class="search-hero">
            <div class="hero-text">
                <h1>Bienvenido a <br>Social Sentiment <span class="highlight">Pulse</span></h1>
                <p>Empieza a analizar la opinión pública en tiempo real.</p>
            </div>

            <!-- SEARCH CARD (Hidden while loading to show progress) -->
            <div v-if="!isLoading" class="search-card glass-card">
                <div class="input-wrapper">
                    <i class="fa-solid fa-magnifying-glass search-icon"></i>
                    <input 
                        type="text" 
                        :value="topic" 
                        @input="$emit('update:topic', $event.target.value)"
                        placeholder="Escribe un tema (ej: Elecciones, iPhone 16...)" 
                        autocomplete="off" 
                        @keyup.enter="startAnalysis"
                    >
                </div>
                
                <div class="options-wrapper">
                    <label><i class="fa-solid fa-filter"></i> Límite de Post por red:</label>
                    <input 
                        type="number" 
                        :value="limit" 
                        @input="$emit('update:limit', parseInt($event.target.value))"
                        min="5" 
                        max="50"
                    >
                </div>

                <button id="analyzeBtn" @click="startAnalysis">
                    <span class="btn-text">Iniciar Análisis Inteligente</span>
                </button>
                
                <p class="status-message" :class="statusColor">{{ statusText }}</p>
            </div>

            <!-- PROGRESS TRACKER (Shown when loading) -->
            <div v-else class="progress-container">
                 <ProgressTracker :topic="topic" apiUrl="http://127.0.0.1:8000" />
                 <p class="status-message" :class="statusColor" style="text-align: center; margin-top: 15px;">{{ statusText }}</p>
            </div>

            <!-- FEATURES GRID (Always visible or maybe hide during load?) -->
            <div v-if="!isLoading" class="features-grid">
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
</template>
