import csv
import multiprocessing
import json
import os
from scrapers.facebook import scrape_facebook
from scrapers.twitter import scrape_twitter
from scrapers.linkedin import scrape_linkedin

import config

# Configuración (En un caso real, usar variables de entorno)
CREDENTIALS = {
    "facebook": {"email": "", "password": ""},
    "twitter": {"username": "", "password": ""},
    "linkedin": {"email": "", "password": ""},
}

import pandas as pd

def worker(platform, topic, creds, limit=15):
    """ Función wrapper para el proceso paralelo """
    print(f"--- Iniciando Worker: {platform} (Meta: {limit}) ---")
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
    
    return data

if __name__ == "__main__":
    # 1. Obtener TEMA
    if config.DEFAULT_TOPIC:
        topic = config.DEFAULT_TOPIC
        print(f"[Config] Usando tema definido: {topic}")
    else:
        topic = input("Introduce el tema a investigar: ")

    # 1b. Obtener CANTIDAD DE POSTS
    try:
        limit_str = input("Introduce la cantidad de posts por plataforma [Default=15]: ")
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
    
    # 3. Configurar LINKEDIN
    if config.LINKEDIN_EMAIL and config.LINKEDIN_PASSWORD:
        CREDENTIALS["linkedin"]["email"] = config.LINKEDIN_EMAIL
        CREDENTIALS["linkedin"]["password"] = config.LINKEDIN_PASSWORD
        print(f"[Config] Credenciales LinkedIn cargadas.")
    # 3. Configurar LINKEDIN
    if config.LINKEDIN_EMAIL and config.LINKEDIN_PASSWORD:
        CREDENTIALS["linkedin"]["email"] = config.LINKEDIN_EMAIL
        CREDENTIALS["linkedin"]["password"] = config.LINKEDIN_PASSWORD
        print(f"[Config] Credenciales LinkedIn cargadas.")
    else:
        # Si no hay credenciales, simplemente saltamos LinkedIn
        pass

    # 4. Configurar LINKEDIN
    if config.LINKEDIN_EMAIL:
         CREDENTIALS["linkedin"]["email"] = config.LINKEDIN_EMAIL
         CREDENTIALS["linkedin"]["password"] = config.LINKEDIN_PASSWORD
         print(f"[Config] Credenciales LinkedIn cargadas para: {config.LINKEDIN_EMAIL}")

    print("\n[Orquestador] Iniciando extracción PARALELA...")
    
    # Crear procesos
    # Usamos multiprocessing para cumplir con el requisito académico
    pool = multiprocessing.Pool(processes=3) # Número de redes a scrapear
    
    tasks = []
    # Tarea Facebook
    tasks.append(pool.apply_async(worker, ("facebook", topic, CREDENTIALS["facebook"], limit)))
    
    # Tarea LinkedIn
    if CREDENTIALS["linkedin"]["email"]:
         tasks.append(pool.apply_async(worker, ("linkedin", topic, CREDENTIALS["linkedin"])))
    
    # Tarea Twitter
    if CREDENTIALS["twitter"]["username"]:
        tasks.append(pool.apply_async(worker, ("twitter", topic, CREDENTIALS["twitter"], limit)))

    # Tarea LinkedIn
    tasks.append(pool.apply_async(worker, ("linkedin", topic, CREDENTIALS["linkedin"], limit)))
    
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
