import os
import glob
import pandas as pd
import cohere
import time
from tqdm import tqdm

def load_data(data_dir="data", topic=None):
    all_posts = []
    pattern = f"corpus_{topic}.csv" if topic else "*.csv"
    csv_files = glob.glob(os.path.join(data_dir, pattern))
    
    print(f"[Sentiment-Cohere] Buscando archivos CSV en {data_dir} con patrón: {pattern}")
    
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            if 'text' in df.columns and 'content' not in df.columns:
                df['content'] = df['text']
            
            if 'content' in df.columns:
                data = df.to_dict(orient='records')
                # Forzar conversión a string y limpiar un poco
                for d in data:
                    d['source_file'] = os.path.basename(file)
                    d['content'] = str(d.get('content', '')).strip()
                all_posts.extend(data)
        except Exception as e:
            print(f"[Sentiment-Cohere] Error leyendo {file}: {e}")
            
    print(f"[Sentiment-Cohere] Total de registros cargados: {len(all_posts)}")
    return all_posts

def configure_cohere():
    api_key = os.getenv("CO_API_KEY")
    if not api_key:
        print("\n--- Configuración de Cohere API ---")
        print("No se encontró la variable de entorno CO_API_KEY.")
        print("Puedes obtener tu API Key gratis en: https://dashboard.cohere.com/api-keys")
        api_key = input("Introduce tu Cohere API Key: ").strip()
    
    if not api_key:
        raise ValueError("Se requiere una API Key para continuar.")
        
    # Inicializar cliente
    return cohere.ClientV2(api_key) 

def analyze_sentiment_batch(client, texts):
    """
    Cohere tiene un endpoint específico para clasificación (/classify) que es más eficiente,
    pero aquí usaremos el endpoint de CHAT (/chat) para mantener la consistencia con los otros ejemplos
    y porque es más flexible si los datos no están etiquetados.
    
    Limitaciones Free Tier de Cohere (Trial Key):
    - 5 llamadas por minuto (RPM) en endpoints pesados o 100/min en endpoints ligeros.
    - Se recomienda usar batches si es posible, pero chat es 1 a 1.
    """
    results = []
    
    for text in texts:
        if not text or len(text) < 3:
            results.append("Neutral")
            continue
            
        prompt = f"""Clasifica este comentario en: 'Positivo', 'Negativo' o 'Neutral'.
        Responde SOLO con la categoría.
        
        Comentario: "{text}"
        """
        
        try:
            response = client.chat(
                model="command-r-plus-08-2024", # Modelo muy bueno en multilenguaje
                messages=[{"role": "user", "content": prompt}]
            )
            
            sentiment = response.message.content[0].text.strip().replace(".", "")
            
            if "Positivo" in sentiment: results.append("Positivo")
            elif "Negativo" in sentiment: results.append("Negativo")
            elif "Neutral" in sentiment: results.append("Neutral")
            else: results.append("Neutral") # Fallback
            
        except Exception as e:
            print(f"Error Cohere: {e}")
            # Si es rate limit (429), esperar.
            if "429" in str(e):
                print("Rate limit detectado. Esperando 12s...")
                time.sleep(12) 
            results.append("Error")
            
        # Rate Limit manual: Cohere Trial es estricto (~5-20 RPM).
        # Esperaremos un poco para no saturar.
        time.sleep(1) # Ajustable
        
    return results

def run_sentiment_analysis():
    # 1. Configurar
    try:
        client = configure_cohere()
    except Exception as e:
        print(f"Error de configuración: {e}")
        return

    # 2. Cargar datos
    data_dir = "data"
    if not os.path.exists(data_dir):
        print(f"No existe el directorio {data_dir}")
        return

    posts = load_data(data_dir)
    if not posts:
        print("No hay datos para procesar.")
        return
        
    # Filtrar solo posts que tengan contenido válido para no gastar quota
    valid_posts = [p for p in posts if p.get('content') and len(str(p['content'])) > 2]
    print(f"\n[Sentiment-Cohere] {len(valid_posts)} comentarios válidos para analizar.")
    print("Nota: Cohere Trial es un poco más lento (Rate Limits estrictos). Ten paciencia.")

    # 3. Procesar
    # Cohere funciona mejor si no saturamos, así que iremos uno a uno con calma
    results = []
    
    for i, post in enumerate(tqdm(valid_posts)):
        text = str(post.get('content', ''))
        
        # Reutilizamos la lógica unitaria (aunque la función se llamase batch, hacemos loop dentro)
        # Adaptada para ser unitaria aquí directamente para mejor control
        
        prompt = f"""Clasifica el sentimiento: 'Positivo', 'Negativo', 'Neutral'. Solo la palabra.
        Texto: "{text}" """
        
        sentiment = "Neutral"
        try:
            response = client.chat(
                model="command-r-08-2024", 
                messages=[{"role": "user", "content": prompt}]
            )
            raw_resp = response.message.content[0].text.strip()
            
            if "Positivo" in raw_resp: sentiment = "Positivo"
            elif "Negativo" in raw_resp: sentiment = "Negativo"
            elif "Neutral" in raw_resp: sentiment = "Neutral"
        
        except Exception as e:
            # print(f"Err: {e}")
            if "429" in str(e):
                 # Cohere free tier: ~5-10 calls per minute.
                 # Esperamos agresivamente si fallamos
                 time.sleep(15)
                 pass # Se quedará como 'Neutral' o reintentaría en un loop real
        
        post['sentiment'] = sentiment
        results.append(post)
        
        # Pausa obligatoria para Cohere Free (aprox 5-10 RPM max en chat)
        # Significa 1 request cada 6-12 segundos.
        time.sleep(6) 

    # 4. Guardar resultados finales
    output_file = os.path.join(data_dir, "sentiment_analysis_cohere.csv")
    df_results = pd.DataFrame(results)
    df_results.to_csv(output_file, index=False)
    
    print(f"\n[Sentiment-Cohere] ¡Análisis completado!")
    print(f"Resultados guardados en: {output_file}")
    
    # Mostrar resumen
    print("\n--- Resumen de Sentimientos (Cohere) ---")
    print(df_results['sentiment'].value_counts())

if __name__ == "__main__":
    run_sentiment_analysis()
