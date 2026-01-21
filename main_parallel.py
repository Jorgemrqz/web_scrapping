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
        if creds['username']:
            data = scrape_twitter(topic, creds['username'], creds['password'], target_count=limit)
        else:
            print(f"[{platform}] Salteando (sin credenciales)")
    elif platform == "linkedin":
        if creds['email'] or True: # Permitir intento con cookies guardadas
            data = scrape_linkedin(topic, creds['email'], creds['password'], target_count=limit)
    elif platform == "instagram":
        data = scrape_instagram(topic, creds['username'], creds['password'], target_count=limit)
    
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
    
    # 2. Configurar FACEBOOK
    if config.FB_EMAIL and config.FB_PASSWORD:
        CREDENTIALS["facebook"]["email"] = config.FB_EMAIL
        CREDENTIALS["facebook"]["password"] = config.FB_PASSWORD
        print(f"[Config] Credenciales Facebook cargadas.")
    else:
        pass # Input manual... omitido por brevedad
    
    # 3. Configurar LINKEDIN/TWITTER
    if config.LINKEDIN_EMAIL and config.LINKEDIN_PASSWORD:
        CREDENTIALS["linkedin"]["email"] = config.LINKEDIN_EMAIL
        CREDENTIALS["linkedin"]["password"] = config.LINKEDIN_PASSWORD
        print(f"[Config] Credenciales LinkedIn cargadas.")

    if config.X_USER:
        CREDENTIALS["twitter"]["username"] = config.X_USER
        CREDENTIALS["twitter"]["password"] = config.X_PASSWORD
        print(f"[Config] Credenciales Twitter cargadas.")
    
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
        try:
            df = pd.DataFrame(all_data)
            excel_filename = f"data/corpus_{topic}.xlsx"
            csv_filename = f"data/corpus_{topic}.csv"
            
            # Limpiar caracteres ilegales para Excel
            # (Excel no soporta ciertos caracteres de control)
            df = df.applymap(lambda x: x.encode('unicode_escape').decode('utf-8') if isinstance(x, str) else x)

            df.to_excel(excel_filename, index=False)
            df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
            print(f"[Export] Datos exportados también a {excel_filename} y {csv_filename}")
        except Exception as e:
            print(f"[Export Error] No se pudo exportar a Excel/CSV: {e}")

    # 4. Ejecutar Pipeline de NLP
    print("\n[Orquestador] Iniciando procesamiento de NLP...")
    try:
        nlp_pipeline.run_nlp_pipeline(topic=topic)
    except Exception as e:
        print(f"[NLP Error] Fallo en el pipeline de NLP: {e}")
