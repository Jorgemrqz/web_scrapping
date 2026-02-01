<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
    dashboardData: Object
});

const platformFilter = ref('all');
const sentimentFilter = ref('all');
const currentPage = ref(1);
const itemsPerPage = 5;

// Computed Properties for filtering and pagination
const filteredData = computed(() => {
    if (!props.dashboardData) return [];
    
    return props.dashboardData.data_preview.filter(row => {
        const matchPlatform = platformFilter.value === 'all' || row.platform.toLowerCase() === platformFilter.value.toLowerCase();
        const matchSentiment = sentimentFilter.value === 'all' || (row.sentiment_llm && row.sentiment_llm.includes(sentimentFilter.value));
        return matchPlatform && matchSentiment;
    });
});

const totalPages = computed(() => Math.ceil(filteredData.value.length / itemsPerPage));

const paginatedData = computed(() => {
    const start = (currentPage.value - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    return filteredData.value.slice(start, end);
});

// Watchers
watch([platformFilter, sentimentFilter], () => {
    currentPage.value = 1;
});

// Methods
function nextPage() {
    if (currentPage.value < totalPages.value) currentPage.value++;
}

function prevPage() {
    if (currentPage.value > 1) currentPage.value--;
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

const getPaginatedComments = (post) => {
    // Ensure commentPage exists, injected during loadDashboard in parent or init defaults here?
    // It's safer to init here if missing, but modifying prop is bad.
    // However, `post` is an object inside the prop array. Vue allows distinct mutation of objects in props 
    // but it's not ideal.
    // Better: use a local WeakMap or reactive wrapper.
    // For simplicity given the code, we assume 'commentPage' is added by parent or we handle it.
    // Let's rely on parent injecting it OR handle it via `post.commentPage || 1`.
    
    const page = post.commentPage || 1;
    const start = (page - 1) * 5;
    return (post.comments || []).slice(start, start + 5);
};

// Modifying prop object (post.commentPage) directly is common in simple Vue apps but anti-pattern.
// We will accept it for now as per previous implementation logic.
</script>

<template>
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
                <!-- Iterate over paginatedData instead of filteredData -->
                <template v-for="(post, idx) in paginatedData" :key="idx">
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
                    <!-- Comments Rows (Nested with Pagination) -->
                    <tr v-for="(comment, cIdx) in getPaginatedComments(post)" :key="`${idx}-c-${cIdx}`" class="comment-row">
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
                    <!-- Filler Rows (Maintain constant height) -->
                    <template v-if="post.comments.length > 5 && getPaginatedComments(post).length < 5">
                        <tr v-for="n in (5 - getPaginatedComments(post).length)" :key="`filler-${idx}-${n}`">
                            <td style="padding-left: 30px; border-bottom: 1px dashed var(--glass-border);">&nbsp;</td>
                            <td style="border-bottom: 1px dashed var(--glass-border); color: transparent;">Filler</td>
                            <td style="border-bottom: 1px dashed var(--glass-border);">&nbsp;</td>
                        </tr>
                    </template>

                    <!-- Comment Pagination Controls -->
                    <tr v-if="post.comments.length > 5">
                        <td colspan="3" style="text-align: center; border-bottom: 1px solid var(--glass-border); padding: 8px;">
                            <div style="display: flex; justify-content: center; align-items: center; gap: 15px; font-size: 0.85em; color: var(--text-secondary);">
                                <button 
                                    @click="post.commentPage--" 
                                    :disabled="post.commentPage === 1"
                                    style="background: transparent; border: 1px solid var(--glass-border); color: var(--accent-color); padding: 2px 8px; border-radius: 4px; cursor: pointer;"
                                    :style="{ opacity: post.commentPage === 1 ? 0.5 : 1 }"
                                >
                                    <i class="fa-solid fa-chevron-left"></i>
                                </button>
                                
                                <span>
                                    Pág. {{ post.commentPage }} / {{ Math.ceil(post.comments.length / 5) }}
                                </span>

                                <button 
                                    @click="post.commentPage++" 
                                    :disabled="post.commentPage >= Math.ceil(post.comments.length / 5)"
                                    style="background: transparent; border: 1px solid var(--glass-border); color: var(--accent-color); padding: 2px 8px; border-radius: 4px; cursor: pointer;"
                                    :style="{ opacity: post.commentPage >= Math.ceil(post.comments.length / 5) ? 0.5 : 1 }"
                                >
                                    <i class="fa-solid fa-chevron-right"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                </template>

                <tr v-if="paginatedData.length === 0">
                    <td colspan="3" style="text-align: center; padding: 20px;">No hay datos para mostrar con estos filtros.</td>
                </tr>
            </tbody>
        </table>
        
        <!-- Pagination Controls -->
        <div class="pagination-controls" v-if="totalPages > 1">
            <button :disabled="currentPage === 1" @click="prevPage" title="Anterior"><i class="fa-solid fa-arrow-left"></i> Anterior</button>
            <span style="font-weight: 600; color: var(--accent-color);">Página {{ currentPage }} / {{ totalPages }}</span>
            <button :disabled="currentPage === totalPages" @click="nextPage" title="Siguiente">Siguiente <i class="fa-solid fa-arrow-right"></i></button>
        </div>
    </div>
</template>
