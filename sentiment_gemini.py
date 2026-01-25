import os
import glob
import pandas as pd
import google.generativeai as genai
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

def configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n--- Configuración de Gemini API ---")
        print("No se encontró la variable de entorno GEMINI_API_KEY.")
        print("Puedes obtener tu API Key gratis en: https://aistudio.google.com/app/apikey")
        api_key = input("Introduce tu Gemini API Key: ").strip()
    
    if not api_key:
        raise ValueError("Se requiere una API Key para continuar.")
        
    genai.configure(api_key=api_key)
    
    # Listar modelos disponibles para depuración
    print("\n[Sentiment] Buscando modelos disponibles...")
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
                # print(f" - {m.name}")
    except Exception as e:
        print(f"[Error] No se pudieron listar los modelos: {e}")
        # Intentar fallback directo
        return genai.GenerativeModel('gemini-pro')

    # Seleccionar el mejor modelo disponible
    target_model = 'models/gemini-1.5-flash'
    if target_model not in available_models:
        print(f"[Sentiment] {target_model} no encontrado. Buscando alternativas...")
        
        # Prioridades
        if 'models/gemini-1.5-flash-8b' in available_models:
            target_model = 'models/gemini-1.5-flash-8b'
        elif 'models/gemini-1.5-pro' in available_models:
            target_model = 'models/gemini-1.5-pro'
        elif 'models/gemini-2.0-flash-exp' in available_models: # Versión experimental a veces disponible
             target_model = 'models/gemini-2.0-flash-exp'
        elif 'models/gemini-pro' in available_models:
            target_model = 'models/gemini-pro'
        elif len(available_models) > 0:
            target_model = available_models[0]
        else:
            print("[Advertencia] No se detectaron modelos compatibles. Intentando 'gemini-pro' por defecto.")
            target_model = 'gemini-pro'
    
    print(f"[Sentiment] Usando modelo: {target_model}")
    return genai.GenerativeModel(target_model)

def analyze_sentiment(model, text):
    if not text or len(str(text)) < 3:
        return "Neutral"
        
    prompt = f"""Clasifica el siguiente comentario de una red social en una de estas tres categorías: 'Positivo', 'Negativo' o 'Neutral'.
    Responde ÚNICAMENTE con la palabra de la categoría.
    
    Comentario: "{text}"
    
    Categoría:"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            sentiment = response.text.strip().replace("\n", "").replace(".", "")
            
            # Normalizar respuesta por si acaso
            if "Positivo" in sentiment: return "Positivo"
            if "Negativo" in sentiment: return "Negativo"
            if "Neutral" in sentiment: return "Neutral"
            
            return sentiment
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Resource has been exhausted" in error_str:
                wait_time = 65 # El error pide ~56s, ponemos 65 para asegurar
                print(f"\n[Limit] Cuota excedida (429). Esperando {wait_time}s antes de reintentar...")
                time.sleep(wait_time)
                continue # Reintentar
            else:
                print(f"Error en API: {e}")
                return "Error"
    
    return "Error" # Si fallan todos los reintentos

def run_sentiment_analysis():
    # 1. Configurar
    try:
        model = configure_gemini()
        # Imprimir modelos encontrados para verificar
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

    print(f"\n[Sentiment] Iniciando análisis de {len(posts)} comentarios con Gemini...")
    print("Nota: Si ves pausas largas es porque estamos respetando los límites gratuitos de Google (5 RPM en algunos modelos).")

    results = []
    
    # 3. Procesar (Iteramos con barra de progreso)
    for i, post in enumerate(tqdm(posts)):
        text = post.get('content', '')
        
        # Saltar si ya tiene sentimiento (opcional, por si re-ejecutamos)
        # if 'sentiment' in post: continue

        sentiment = analyze_sentiment(model, text)
        
        post['sentiment'] = sentiment
        results.append(post)
        
        # Respetar Rate Limits. 
        # Si el límite es 5 RPM -> 1 request cada 12 segundos.
        # Ponemos 10s de base para intentar ir un poco más fluido si el token bucket lo permite,
        # confiando en el retry catch si fallamos.
        time.sleep(10) 
        
        # Guardado parcial cada 10 items
        if i > 0 and i % 10 == 0:
             pd.DataFrame(results).to_csv(os.path.join(data_dir, "sentiment_results_partial.csv"), index=False)

    # 4. Guardar resultados finales
    output_file = os.path.join(data_dir, "sentiment_analysis_gemini.csv")
    df_results = pd.DataFrame(results)
    df_results.to_csv(output_file, index=False)
    
    print(f"\n[Sentiment] ¡Análisis completado!")
    print(f"Resultados guardados en: {output_file}")
    
    # Mostrar resumen
    print("\n--- Resumen de Sentimientos ---")
    print(df_results['sentiment'].value_counts())

if __name__ == "__main__":
    run_sentiment_analysis()
