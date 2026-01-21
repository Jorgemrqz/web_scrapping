import json
import os
import re
import glob
import nltk
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from nltk.tokenize import word_tokenize
from collections import Counter

# Descargar recursos de NLTK necesarios (se ejecuta una vez)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    print("[NLP] Descargando recursos de NLTK...")
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('punkt_tab')

def load_data(data_dir="data"):
    all_posts = []
    json_files = glob.glob(os.path.join(data_dir, "*.json"))
    
    print(f"[NLP] Encontrados {len(json_files)} archivos JSON en {data_dir}")
    
    for file in json_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Normalizar si es lista o dict
                if isinstance(data, list):
                    all_posts.extend(data)
                elif isinstance(data, dict):
                    all_posts.append(data)
        except Exception as e:
            print(f"[NLP] Error leyendo {file}: {e}")
            
    print(f"[NLP] Total de registros cargados: {len(all_posts)}")
    return all_posts

def clean_text(text):
    # 1. Convertir a minúsculas
    text = text.lower()
    
    # 2. Eliminar URLs
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    
    # 3. Eliminar menciones (@usuario) y hashtags (#tema) - Opcional, a veces sirven
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'#\w+', '', text)
    
    # 4. Eliminar emoticones y caracteres especiales (dejamos solo letras y espacios)
    text = re.sub(r'[^a-záéíóúñ\s]', '', text)
    
    # 5. Eliminar espacios extra
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def process_nlp(posts):
    # Inicializar herramientas
    stop_words = set(stopwords.words('spanish'))
    # Agregar stopwords personalizadas comunes en redes
    stop_words.update(["si", "q", "ma", "pa", "ver", "mas", "va", "ser", "hacer", "linkedin", "twitter", "facebook"])
    
    stemmer = SnowballStemmer('spanish')
    
    corpus_tokens = []
    processed_docs = []

    print("[NLP] Procesando textos...")
    
    for post in posts:
        original = post.get('content', '') or post.get('text', '')
        if not original:
            continue
            
        # 1. Limpieza
        cleaned = clean_text(original)
        
        # 2. Tokenización
        tokens = word_tokenize(cleaned)
        
        # 3. Remover Stopwords y palabras cortas
        filtered_tokens = [t for t in tokens if t not in stop_words and len(t) > 2]
        
        # 4. Stemming (Convertir a forma canónica)
        # Nota: Para WordCloud a veces es mejor usar lemas o la palabra original limpia, 
        # porque el stemming corta palabras (ej. "inteligencia" -> "intelig").
        # Aquí guardaremos ambos para mostrar.
        stemmed_tokens = [stemmer.stem(t) for t in filtered_tokens]
        
        corpus_tokens.extend(filtered_tokens) # Usamos tokens completos para la nube visual
        processed_docs.append({
            "original": original,
            "cleaned": cleaned,
            "tokens": filtered_tokens,
            "stemmed": stemmed_tokens
        })

    return corpus_tokens, processed_docs

def generate_visualizations(tokens, output_dir="data"):
    if not tokens:
        print("[NLP] No hay suficientes datos para visualizar.")
        return

    # a) Bolsa de Palabras (Frecuencia)
    word_freq = Counter(tokens)
    common_words = word_freq.most_common(20)
    
    print("\n[NLP] Top 20 Palabras más comunes (Bolsa de Palabras):")
    for word, freq in common_words:
        print(f"   {word}: {freq}")
        
    # Graficar Frecuencia
    plt.figure(figsize=(10, 6))
    words, counts = zip(*common_words)
    plt.bar(words, counts)
    plt.title("Top 20 Palabras Frecuentes")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'frecuencia_palabras.png'))
    print(f"[NLP] Gráfico de frecuencias guardado en {output_dir}/frecuencia_palabras.png")
    
    # b) Nube de Palabras
    text_for_cloud = " ".join(tokens)
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text_for_cloud)
    
    plt.figure(figsize=(10, 6))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    plt.title("Nube de Palabras")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'wordcloud.png'))
    print(f"[NLP] WordCloud guardado en {output_dir}/wordcloud.png")

if __name__ == "__main__":
    # Asegurar directorio de datos
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Cargar datos
    data = load_data()
    
    if data:
        # Procesar
        all_tokens, processed_data = process_nlp(data)
        
        # Visualizar
        generate_visualizations(all_tokens)
        
        print("\n[NLP] Pipeline finalizado exitosamente.")
    else:
        print("[NLP] No se encontraron datos para procesar. Ejecuta primero main_parallel.py")
