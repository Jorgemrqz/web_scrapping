import multiprocessing
import json
import os
from datetime import datetime
from scrapers.facebook import scrape_facebook
from scrapers.twitter import scrape_twitter
from scrapers.linkedin import scrape_linkedin
from scrapers.instagram import scrape_instagram
import nlp_pipeline

import config

# Configuración (En un caso real, usar variables de entorno)
CREDENTIALS = {
    "facebook": {"email": "", "password": ""},
    "twitter": {"username": "", "password": ""},
    "linkedin": {"email": "", "password": ""},
    "instagram": {"username": "", "password": ""},
}

import pandas as pd

def worker(platform, topic, creds, limit=15):
    """ Función wrapper para el proceso paralelo """
    start_time = datetime.now().strftime("%H:%M:%S")
    print(f"[{start_time}] --- Iniciando Worker: {platform} (Meta: {limit}) ---")
    data = []
    
    if platform == "facebook":
        data = scrape_facebook(topic, creds['email'], creds['password'], target_count=limit)
    elif platform == "twitter":
        t_user = creds.get('email') or creds.get('username')
        if t_user:
            data = scrape_twitter(topic, t_user, creds['password'], target_count=limit)
        else:
            print(f"[{platform}] Salteando (sin credenciales)")
    elif platform == "linkedin":
        if creds['email'] or True: # Permitir intento con cookies guardadas
            data = scrape_linkedin(topic, creds['email'], creds['password'], target_count=limit)
    elif platform == "instagram":
        i_user = creds.get('username') or creds.get('email')
        data = scrape_instagram(topic, i_user, creds['password'], target_count=limit)
    
    return data

if __name__ == "__main__":
    # 1. Obtener TEMA
    default_t = config.DEFAULT_TOPIC if config.DEFAULT_TOPIC else ""
    prompt_text = f"Introduce el tema a investigar [Enter para '{default_t}']: " if default_t else "Introduce el tema a investigar: "
    
    topic_input = input(prompt_text).strip()
    
    if topic_input:
        topic = topic_input
    elif default_t:
        topic = default_t
        print(f"[Config] Usando tema por defecto: {topic}")
    else:
        print("Error: Debes introducir un tema.")
        exit()

    # 1b. Obtener CANTIDAD DE POSTS
    try:
        limit_str = input("Introduce la cantidad de posts por plataforma [Default=10]: ")
        if not limit_str.strip():
            limit = 10
        else:
            limit = int(limit_str)
    except:
        limit = 10
    
    print(f"[Config] Meta unificada: {limit} posts por red.")
    
    print(f"[Config] Meta unificada: {limit} posts por red.")
    
    # 2. Cargar Credenciales desde Config Centralizado
    CREDENTIALS = config.CREDENTIALS
    
    print("\n[Orquestador] Iniciando extracción PARALELA...")
    
    print("\n[Orquestador] Iniciando extracción PARALELA...")
    
    # Crear procesos
    # Usamos multiprocessing para cumplir con el requisito académico
    pool = multiprocessing.Pool(processes=4) # Número de redes a scrapear
    
    tasks = []
    # Tarea Facebook
    tasks.append(pool.apply_async(worker, ("facebook", topic, CREDENTIALS["facebook"], limit)))
    
    # Tarea Twitter
    if CREDENTIALS["twitter"]["username"]:
        tasks.append(pool.apply_async(worker, ("twitter", topic, CREDENTIALS["twitter"], limit)))

    # Tarea LinkedIn
    # Se añade siempre, el worker decide si tiene credenciales o intenta con cookies
    tasks.append(pool.apply_async(worker, ("linkedin", topic, CREDENTIALS["linkedin"], limit)))

    tasks.append(pool.apply_async(worker, ("instagram", topic, CREDENTIALS["instagram"], limit)))
    
    # Recolectar resultados
    all_data = []
    for task in tasks:
        try:
            res = task.get(timeout=1800) # Timeout aumentado (30 min) para scraping largo
            all_data.extend(res)
        except Exception as e:
            print(f"Error en un worker: {e}")
            
    pool.close()
    pool.join()
    
    # Guardar Corpus JSON
    os.makedirs("data", exist_ok=True)
    json_filename = f"data/corpus_{topic}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n[Terminado] Se han guardado {len(all_data)} registros en {json_filename}")

    # exportar a Excel / CSV
    if all_data:
       # Create DataFrame
        df = pd.DataFrame(all_data)

        # ---------------------------------------------------------
        # FASE 2: PROCESAMIENTO CON LLMs (Práctica 06)
        # ---------------------------------------------------------
        try:
            from llm_processor import process_dataframe_concurrently
            print("\n[INFO] Iniciando Fase 2: Clasificación de Sentimiento con LLMs...")
            df = process_dataframe_concurrently(df)
            print("[INFO] Fase 2 completada.")
        except Exception as e:
            print(f"\n[WARN] No se pudo ejecutar el análisis de LLMs: {e}")
            print("Continuando con la exportación solo de datos scrapeados...")

        # Reorder columns if desired
        # Expected columns: platform, post_index, post_author, post_content, comment_author, comment_content, sentiment_llm, explanation_llm
        cols = ['platform', 'sentiment_llm', 'explanation_llm', 'post_index', 'post_author', 'post_content', 'comment_author', 'comment_content']
        # Filter to only existing columns
        cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols and c not in ['sentiment_llm', 'explanation_llm']]
        
        df = df[cols]

        # Export
        print("Exporting data...")

        # 1. Excel (requires openpyxl)
        try:
            excel_name = f"corpus_{topic}.xlsx"
            df.to_excel(os.path.join("data", excel_name), index=False)
            print(f"Saved Excel: {excel_name}")
        except Exception as e:
            print(f"Could not save Excel: {e}")

        # 2. CSV
        try:
            csv_name = f"corpus_{topic}.csv"
            # Escape special characters to avoid breaking CSV format
            # Use simple str() conversion or specific replacement
            df.to_csv(os.path.join("data", csv_name), index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
            print(f"Saved CSV: {csv_name}")
        except Exception as e:
            print(f"Could not save CSV: {e}")
            try:
               # Fallback for older pandas versions usually not needed but safety first
               print("Standard export failed, trying alternative...")
               # This line was problematic in the original snippet, fixing it to be valid Python
               df_cleaned = df.applymap(lambda x: x.encode('unicode_escape').decode('utf-8') if isinstance(x, str) else x)
               df_cleaned.to_csv(os.path.join("data", csv_name), index=False, encoding='utf-8-sig')
            except Exception as inner_e:
               print(f"Alternative CSV export also failed: {inner_e}")


    # 4. Ejecutar Pipeline de NLP
    print("\n[Orquestador] Iniciando procesamiento de NLP...")
    try:
        nlp_pipeline.run_nlp_pipeline(topic=topic)
    except Exception as e:
        print(f"[NLP Error] Fallo en el pipeline de NLP: {e}")
