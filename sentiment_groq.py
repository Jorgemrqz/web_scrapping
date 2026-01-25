import os
import glob
import pandas as pd
from groq import Groq
import time
from tqdm import tqdm

def load_data(data_dir="data", topic=None):
    all_posts = []
    pattern = f"corpus_{topic}.csv" if topic else "*.csv"
    csv_files = glob.glob(os.path.join(data_dir, pattern))
    
    print(f"[Sentiment] Buscando archivos CSV en {data_dir} con patrón: {pattern}")
    
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            # Normalizar nombres de columnas
            if 'text' in df.columns and 'content' not in df.columns:
                df['content'] = df['text']
            
            # Asegurarnos de que tenga contenido
            if 'content' in df.columns:
                data = df.to_dict(orient='records')
                # Añadir nombre de archivo para referencia
                for d in data:
                    d['source_file'] = os.path.basename(file)
                all_posts.extend(data)
        except Exception as e:
            print(f"[Sentiment] Error leyendo {file}: {e}")
            
    print(f"[Sentiment] Total de registros cargados: {len(all_posts)}")
    return all_posts

def configure_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\n--- Configuración de Groq API ---")
        print("No se encontró la variable de entorno GROQ_API_KEY.")
        print("Puedes obtener tu API Key gratis en: https://console.groq.com/keys")
        api_key = input("Introduce tu Groq API Key: ").strip()
    
    if not api_key:
        raise ValueError("Se requiere una API Key para continuar.")
        
    return Groq(api_key=api_key)

def analyze_sentiment(client, text):
    if not text or len(str(text)) < 3:
        return "Neutral"
        
    prompt = f"""Clasifica el siguiente comentario de una red social en una de estas tres categorías: 'Positivo', 'Negativo' o 'Neutral'.
    Responde ÚNICAMENTE con la palabra de la categoría. Si no estás seguro, responde 'Neutral'.
    
    Comentario: "{text}"
    
    Categoría:"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile", # Modelo actualizado
                temperature=0,
                max_tokens=10,
            )
            
            sentiment = chat_completion.choices[0].message.content.strip().replace("\n", "").replace(".", "")
            
            # Limpieza básica
            if "Positivo" in sentiment: return "Positivo"
            if "Negativo" in sentiment: return "Negativo"
            if "Neutral" in sentiment: return "Neutral"
            
            return sentiment
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str: # Rate limit
                wait_time = 5 * (attempt + 1)
                print(f"\n[Limit] Rate limit (429). Esperando {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"Error en API: {e}")
                return "Error"
                
    return "Error"

def run_sentiment_analysis():
    # 1. Configurar
    try:
        client = configure_groq()
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

    print(f"\n[Sentiment] Iniciando análisis de {len(posts)} comentarios con Groq (Llama 3)...")
    print("Groq es extremadamente rápido, procesaremos esto en segundos.")

    results = []
    
    # 3. Procesar
    # Groq es tan rápido que podemos ir con muy poco delay, pero por seguridad y limites gratuitos:
    # Free tier: 30 requests per minute aprox en algunos modelos, pero 14400 requests/day.
    # Llama3-70b suele tener límites decentes.
    
    for i, post in enumerate(tqdm(posts)):
        text = post.get('content', '')
        
        sentiment = analyze_sentiment(client, text)
        
        post['sentiment'] = sentiment
        results.append(post)
        
        # Pequeño delay de 1.5s para no saturar el RPM (Rate Per Minute)
        # Groq permite unas 30 RPM en free tier para modelos grandes.
        time.sleep(2) 
        
        # Guardado parcial cada 50 items
        if i > 0 and i % 50 == 0:
             pd.DataFrame(results).to_csv(os.path.join(data_dir, "sentiment_results_partial_groq.csv"), index=False)

    # 4. Guardar resultados finales
    output_file = os.path.join(data_dir, "sentiment_analysis_groq.csv")
    df_results = pd.DataFrame(results)
    df_results.to_csv(output_file, index=False)
    
    print(f"\n[Sentiment] ¡Análisis completado!")
    print(f"Resultados guardados en: {output_file}")
    
    # Mostrar resumen
    print("\n--- Resumen de Sentimientos ---")
    print(df_results['sentiment'].value_counts())

if __name__ == "__main__":
    run_sentiment_analysis()
