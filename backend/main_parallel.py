import multiprocessing
import json
import os
import time
import csv
from datetime import datetime
import pandas as pd

from scrapers.facebook import scrape_facebook
from scrapers.twitter import scrape_twitter
from scrapers.linkedin import scrape_linkedin
from scrapers.instagram import scrape_instagram
import nlp_pipeline
from llm_processor import process_dataframe_concurrently
from analysis import perform_analysis
import config

# Configuración (En un caso real, usar variables de entorno)
CREDENTIALS = config.CREDENTIALS

def worker(platform, topic, credentials, limit=15):
    """ Función wrapper para el proceso paralelo """
    # Nota: Si se llama desde API, multiprocessing puede tener problemas con prints,
    # pero lo dejaremos para debugging.
    print(f"[{platform.capitalize()}] Iniciando worker...")
    try:
        # DB connection for worker
        try:
             from database import Database
             db = Database()
        except: db = None

        # Helper to get user/email
        def get_user(c): return c.get("username") or c.get("email") or ""

        # Update DB status to 'running' generic for worker start (failsafe)
        if db and db.is_connected:
             db.update_stage_progress(topic, platform, 0, "running")

        if platform == "facebook":
            # from scrapers.facebook import scrape_facebook # Already imported at top
            return scrape_facebook(topic, credentials.get("email"), credentials.get("password"), limit)
        elif platform == "twitter":
            # from scrapers.twitter import scrape_twitter # Already imported at top
            return scrape_twitter(topic, get_user(credentials), credentials.get("password"), limit)
        elif platform == "linkedin":
            # from scrapers.linkedin import scrape_linkedin # Already imported at top
            return scrape_linkedin(topic, credentials.get("email"), credentials.get("password"), limit)
        elif platform == "instagram":
            # from scrapers.instagram import scrape_instagram # Already imported at top
            return scrape_instagram(topic, get_user(credentials), credentials.get("password"), limit)
        else:
            print(f"Plataforma desconocida: {platform}")
            return []
    except Exception as e:
        print(f"Error en worker {platform}: {e}")
        return []

def run_pipeline(topic: str, limit: int = 10):
    """
    Función orquestadora principal.
    Scraping -> LLM Processing -> NLP Pipeline -> CSV Export -> Storytelling
    Retorna: Ruta del CSV generado o None si falla.
    """
    print(f"\n[Orquestador] Iniciando extracción PARALELA para '{topic}' (Límite: {limit})...")
    
    # Init DB Status
    try:
        from database import Database
        db = Database()
        if db.is_connected:
            db.init_job_status(topic, ["twitter", "facebook", "linkedin", "instagram"], limit)
    except: db = None

    # Crear procesos
    start_time_scraping = time.time()
    pool = multiprocessing.Pool(processes=4) # 4 Processes
    
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
    
    scraping_duration = time.time() - start_time_scraping
    print(f"\n[Stats] Tiempo total de Scraping: {scraping_duration:.2f} segundos")

    if db and db.is_connected:
        db.update_job_timings(topic, scraping_time=scraping_duration)

    
    unique_posts_count = len(set((x.get('platform'), x.get('post_index')) for x in all_data))
    print(f"\n[Terminado] Se han recolectado {len(all_data)} registros (Comentarios/Interacciones) correspondientes a {unique_posts_count} posts únicos.")
    
    csv_path = None
    
    if all_data:
        # Create DataFrame
        df = pd.DataFrame(all_data)

        # FASE 2: PROCESAMIENTO CON LLMs 
        llm_duration = 0
        try:
            print("\n[INFO] Iniciando Fase 2: Clasificación de Sentimiento con LLMs...")
            if db and db.is_connected:
                db.update_llm_status(topic, "running")

            start_time_llm = time.time()
            df = process_dataframe_concurrently(df)
            llm_duration = time.time() - start_time_llm
            print(f"[Stats] Tiempo total de Clasificación LLM: {llm_duration:.2f} segundos")
            
            if db and db.is_connected:
                db.update_llm_status(topic, "completed")
                db.update_job_timings(topic, llm_time=llm_duration)
            print("[INFO] Fase 2 completada.")
        except Exception as e:
            print(f"\n[WARN] No se pudo ejecutar el análisis de LLMs: {e}")

        # Reorder/Filter columns
        cols = ['platform', 'sentiment_llm', 'explanation_llm', 'tokens_llm', 'post_index', 'post_author', 'post_content', 'comment_author', 'comment_content']
        cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols and c not in ['sentiment_llm', 'explanation_llm', 'tokens_llm']]
        df = df[cols]

        # Export JSON (Structured)
        try:
            # Nesting Data: Group by Post Content/Author/Platform
            # We assume 'post_content' + 'platform' is unique enough for this session
            structured_data = []
            
            # Fill NaN with empty string to avoid grouping errors
            df.fillna("", inplace=True)
            
            # Create a unique group key
            if 'post_index' in df.columns:
                 grouped = df.groupby(['platform', 'post_index'])
            else:
                 grouped = df.groupby(['platform', 'post_content'])
                 
            for name, group in grouped:
                first_row = group.iloc[0]
                post_obj = {
                    "platform": first_row.get('platform', ''),
                    "author": first_row.get('post_author', ''),
                    "content": first_row.get('post_content', ''),
                    "sentiment_llm": group['sentiment_llm'].mode()[0] if not group['sentiment_llm'].empty else "", # Post sentiment (heuristic)
                    "comments": []
                }
                
                # Add comments
                for _, row in group.iterrows():
                    if row.get('comment_content'):
                        post_obj["comments"].append({
                            "author": row.get('comment_author', ''),
                            "content": row.get('comment_content', ''),
                            "sentiment": row.get('sentiment_llm', '') # Comment specific sentiment
                        })
                
                structured_data.append(post_obj)

            # --- GUARDADO EN MONGODB (PRIMARIO) ---
            print(f"[Export] Guardando {len(structured_data)} posts estructurados en MongoDB...")
            try:
                from database import Database
                db = Database() # Intenta conectar a localhost por defecto
                if db.is_connected:
                    db.save_corpus(topic, structured_data)
                else:
                     print("[Error] No hay conexión a MongoDB. Los datos no se persistirán.")
            except Exception as e:
                print(f"[MongoDB Integration Error] {e}")
            # --------------------------------------

            # Return success indicator
            csv_path = "mongodb_stored"
            
        except Exception as e:
            print(f"Could not structure/save data: {e}")
            import traceback
            traceback.print_exc()

    # 4. Ejecutar Pipeline de NLP
    print("\n[Orquestador] Iniciando procesamiento de NLP...")
    try:
        nlp_pipeline.run_nlp_pipeline(topic=topic)
    except Exception as e:
        print(f"[NLP Error] Fallo en el pipeline de NLP: {e}")
        
    # 5. Ejecutar Análisis Agregado y Storytelling
    if df is not None and not df.empty:
        try:
            print("\n[Orquestador] Generando Informe Ejecutivo (Storytelling)...")
            # Pass DF directly to avoid re-reading
            timings = {"scraping": scraping_duration, "llm": llm_duration}
            perform_analysis(None, topic, df=df, timings=timings)
        except Exception as e:
             print(f"[Analysis Error] No se pudo generar el reporte JSON: {e}")

    # Guardar Tiempos en CSV local (data/execution_times.csv)
    try:
        if not os.path.exists("data"):
            os.makedirs("data")
            
        log_file = "data/execution_times.csv"
        file_exists = os.path.isfile(log_file)
        
        # Variables seguras
        s_dur = scraping_duration if 'scraping_duration' in locals() else 0.0
        l_dur = llm_duration if 'llm_duration' in locals() else 0.0
        rec_count = len(all_data) if 'all_data' in locals() else 0
        
        with open(log_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Topic", "Limit", "Scraping_Time_Sec", "LLM_Time_Sec", "Total_Records"])
            
            writer.writerow([
                datetime.now().isoformat(),
                topic,
                limit, 
                f"{s_dur:.2f}",
                f"{l_dur:.2f}",
                rec_count
            ])
            print(f"[Stats] Tiempos registrados en '{log_file}'")
    except Exception as e:
        print(f"[Error] No se pudo guardar el log CSV: {e}")

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
    
    # 3. Ejecutar Pipeline
    result_csv = run_pipeline(topic, limit)
    
    if result_csv:
        print(f"\n[EXITO] Proceso completo. Resultado en: {result_csv}")
    else:
        print("\n[FIN] Proceso terminado sin generar CSV final (posiblemente sin datos).")
