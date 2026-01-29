import multiprocessing
import json
import os
from datetime import datetime
import pandas as pd

from scrapers.facebook import scrape_facebook
from scrapers.twitter import scrape_twitter
from scrapers.linkedin import scrape_linkedin
from scrapers.instagram import scrape_instagram
import nlp_pipeline
from llm_processor import process_dataframe_concurrently
import config

# Configuración (En un caso real, usar variables de entorno)
CREDENTIALS = config.CREDENTIALS

def worker(platform, topic, creds, limit=15):
    """ Función wrapper para el proceso paralelo """
    # Nota: Si se llama desde API, multiprocessing puede tener problemas con prints,
    # pero lo dejaremos para debugging.
    start_time = datetime.now().strftime("%H:%M:%S")
    print(f"[{start_time}] --- Iniciando Worker: {platform} (Meta: {limit}) ---")
    data = []
    
    try:
        if platform == "facebook":
            data = scrape_facebook(topic, creds['email'], creds['password'], target_count=limit)
        elif platform == "twitter":
            t_user = creds.get('email') or creds.get('username') or "CookieSession"
            data = scrape_twitter(topic, t_user, creds['password'], target_count=limit)
        elif platform == "linkedin":
            li_limit = limit * 1
            print(f"[{platform}] Ajustando meta a {li_limit} posts (x5) para compensar volumen.")
            data = scrape_linkedin(topic, creds['email'], creds['password'], target_count=li_limit)
        elif platform == "instagram":
            i_user = creds.get('username') or creds.get('email')
            data = scrape_instagram(topic, i_user, creds['password'], target_count=limit)
    except Exception as e:
        print(f"[Error Worker {platform}] {e}")
        # Retornamos lista vacía en caso de error para no romper todo
        return []
    
    return data

def run_pipeline(topic: str, limit: int = 10):
    """
    Función orquestadora principal.
    Scraping -> LLM Processing -> NLP Pipeline -> CSV Export
    Retorna: Ruta del CSV generado o None si falla.
    """
    print(f"\n[Orquestador] Iniciando extracción PARALELA para '{topic}' (Límite: {limit})...")
    
    # Crear procesos
    pool = multiprocessing.Pool(processes=4) # Número de redes a scrapear
    
    tasks = []
    # Tarea Facebook
    tasks.append(pool.apply_async(worker, ("facebook", topic, CREDENTIALS["facebook"], limit)))
    
    # Tarea Twitter
    tasks.append(pool.apply_async(worker, ("twitter", topic, CREDENTIALS["twitter"], limit)))

    # Tarea LinkedIn
    tasks.append(pool.apply_async(worker, ("linkedin", topic, CREDENTIALS["linkedin"], limit)))

    # Tarea Instagram
    tasks.append(pool.apply_async(worker, ("instagram", topic, CREDENTIALS["instagram"], limit)))
    
    # Recolectar resultados
    all_data = []
    for task in tasks:
        try:
            res = task.get(timeout=1800) 
            if res:
                all_data.extend(res)
        except Exception as e:
            print(f"Error en un worker: {e}")
            
    pool.close()
    pool.join()
    
    print(f"\n[Terminado] Se han recolectado {len(all_data)} registros.")
    
    csv_path = None
    
    if all_data:
        # Create DataFrame
        df = pd.DataFrame(all_data)

        # FASE 1.5: GUARDADO INTERMEDIO (SEGURIDAD)
        os.makedirs("data", exist_ok=True)
        try:
            raw_csv_name = f"corpus_{topic}_raw.csv"
            raw_path = os.path.join("data", raw_csv_name)
            df.to_csv(raw_path, index=False, encoding='utf-8-sig')
            print(f"[Backup] Datos crudos guardados en: {raw_csv_name}")
        except Exception as e:
            print(f"[Backup Error] No se pudo guardar copia de seguridad: {e}")

        # FASE 2: PROCESAMIENTO CON LLMs 
        try:
            print("\n[INFO] Iniciando Fase 2: Clasificación de Sentimiento con LLMs...")
            df = process_dataframe_concurrently(df)
            print("[INFO] Fase 2 completada.")
        except Exception as e:
            print(f"\n[WARN] No se pudo ejecutar el análisis de LLMs: {e}")

        # Reorder/Filter columns
        cols = ['platform', 'sentiment_llm', 'explanation_llm', 'tokens_llm', 'post_index', 'post_author', 'post_content', 'comment_author', 'comment_content']
        cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols and c not in ['sentiment_llm', 'explanation_llm', 'tokens_llm']]
        df = df[cols]

        # Export CSV Final
        try:
            csv_name = f"corpus_{topic}.csv"
            csv_path = os.path.join("data", csv_name)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"Saved CSV: {csv_name}")
        except Exception as e:
            print(f"Could not save CSV: {e}")

    # 4. Ejecutar Pipeline de NLP (Genera gráficas)
    print("\n[Orquestador] Iniciando procesamiento de NLP...")
    try:
        nlp_pipeline.run_nlp_pipeline(topic=topic)
    except Exception as e:
        print(f"[NLP Error] Fallo en el pipeline de NLP: {e}")
        
    return csv_path

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
    
    # 2. Cargar Credenciales (Globales ya cargadas arriba pero por claridad)
    # 3. Ejecutar Pipeline
    result_csv = run_pipeline(topic, limit)
    
    if result_csv:
        print(f"\n[EXITO] Proceso completo. Resultado en: {result_csv}")
    else:
        print("\n[FIN] Proceso terminado sin generar CSV final (posiblemente sin datos).")
