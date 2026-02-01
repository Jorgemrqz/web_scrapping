<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';

const props = defineProps({
    topic: String,
    apiUrl: String
});

const status = ref(null);
const polling = ref(null);

const stages = computed(() => {
    if (!status.value || !status.value.stages) {
        // Default stages structure for mockup if DB is empty initially
        return {
            "twitter": { current: 0, total: 0, status: 'pending' },
            "facebook": { current: 0, total: 0, status: 'pending' },
            "linkedin": { current: 0, total: 0, status: 'pending' },
            "instagram": { current: 0, total: 0, status: 'pending' }
        };
    }
    return status.value.stages;
});

const llmStatus = computed(() => status.value?.llm_status || 'pending');

function getIcon(platform) {
    const p = platform.toLowerCase();
    if (p.includes('twitter') || p.includes('x')) return 'fa-brands fa-x-twitter'; // Use x-twitter or twitter
    if (p.includes('facebook')) return 'fa-brands fa-facebook';
    if (p.includes('linkedin')) return 'fa-brands fa-linkedin';
    if (p.includes('instagram')) return 'fa-brands fa-instagram';
    if (p.includes('tiktok')) return 'fa-brands fa-tiktok';
    return 'fa-solid fa-globe';
}

function getStatusIcon(stageStatus) {
    if (stageStatus === 'completed') return 'fa-solid fa-circle-check has-text-success';
    if (stageStatus === 'running') return 'fa-solid fa-spinner fa-spin';
    return 'fa-regular fa-circle';
}

function pollStatus() {
    polling.value = setInterval(async () => {
        try {
            const res = await fetch(`${props.apiUrl}/status/${props.topic}`);
            if (res.ok) {
                status.value = await res.json();
            }
        } catch (e) {
            console.error("Status check failed", e);
        }
    }, 1000);
}

onMounted(() => {
    pollStatus();
});

onUnmounted(() => {
    if (polling.value) clearInterval(polling.value);
});
</script>

<template>
    <div class="progress-box glass-card">
        <h3><i class="fa-solid fa-microchip"></i> Estado del Análisis</h3>
        
        <div class="stages-list">
            <div v-for="(data, platform) in stages" :key="platform" class="stage-item" :class="{ 'active': data.status === 'running', 'done': data.status === 'completed' }">
                <div class="stage-icon">
                    <i :class="getIcon(platform)"></i>
                </div>
                <div class="stage-info">
                    <span class="stage-name">{{ platform.charAt(0).toUpperCase() + platform.slice(1) }}</span>
                    <span class="stage-count">{{ data.current }} / {{ data.total }} posts</span>
                </div>
                <div class="stage-status">
                     <i :class="getStatusIcon(data.status)"></i>
                </div>
            </div>
            
            <div class="divider"></div>

            <div class="stage-item" :class="{ 'active': llmStatus === 'running', 'done': llmStatus === 'completed' }">
                 <div class="stage-icon">
                    <i class="fa-solid fa-brain"></i>
                </div>
                <div class="stage-info">
                    <span class="stage-name">Análisis Inteligente (LLM)</span>
                    <span class="stage-count" v-if="llmStatus === 'running'">Clasificando sentimientos...</span>
                    <span class="stage-count" v-if="llmStatus === 'completed'">Finalizado</span>
                    <span class="stage-count" v-if="llmStatus === 'pending'">En espera...</span>
                </div>
                <div class="stage-status">
                     <i :class="getStatusIcon(llmStatus)"></i>
                </div>
            </div>

        </div>
    </div>
</template>

<style scoped>
.progress-box {
    margin-top: 20px;
    padding: 20px;
    animation: fadeIn 0.5s ease;
    border: 1px solid rgba(16, 185, 129, 0.2); /* Green tint hint */
}

.progress-box h3 {
    font-size: 1rem;
    margin-bottom: 15px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 10px;
}

.stages-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.stage-item {
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 10px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.03);
    transition: all 0.3s ease;
}

.stage-item.active {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.2);
}

.stage-item.done {
    background: rgba(16, 185, 129, 0.05);
    opacity: 0.8;
}

.stage-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: rgba(255,255,255,0.05);
    color: var(--text-secondary);
}

.stage-item.active .stage-icon {
    color: var(--accent-color);
    background: rgba(59, 130, 246, 0.2);
}

.stage-item.done .stage-icon {
    color: var(--success);
    background: rgba(16, 185, 129, 0.2);
}

.stage-info {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.stage-name {
    font-weight: 600;
    font-size: 0.9em;
}

.stage-count {
    font-size: 0.8em;
    color: var(--text-secondary);
}

.stage-status i {
    font-size: 1.1em;
    color: var(--text-secondary);
}

.has-text-success {
    color: var(--success) !important;
}

.divider {
    height: 1px;
    background: rgba(255,255,255,0.1);
    margin: 5px 0;
}
</style>
