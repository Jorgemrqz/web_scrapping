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

def worker(platform, topic, creds):
    """ Función wrapper para el proceso paralelo """
    print(f"--- Iniciando Worker: {platform} ---")
    data = []
    
    if platform == "facebook":
        data = scrape_facebook(topic, creds['email'], creds['password'])
    elif platform == "twitter":
        if creds['username']:
            data = scrape_twitter(topic, creds['username'], creds['password'])
    elif platform == "linkedin":
        if creds['email']:
            data = scrape_linkedin(topic, creds['email'], creds['password'])
        else:
            print("[LinkedIn] Salteando (sin email)")
    
    return data

if __name__ == "__main__":
    # 1. Obtener TEMA
    if config.DEFAULT_TOPIC:
        topic = config.DEFAULT_TOPIC
        print(f"[Config] Usando tema definido: {topic}")
    else:
        topic = input("Introduce el tema a investigar: ")
    
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

    # 4. Configurar TWITTER...
    
    print("\n[Orquestador] Iniciando extracción PARALELA...")
    
    # Crear procesos
    pool = multiprocessing.Pool(processes=3) # FB + TW + LI
    
    tasks = []
    # Tarea Facebook (ACTIVADA)
    tasks.append(pool.apply_async(worker, ("facebook", topic, CREDENTIALS["facebook"])))
    
    # Tarea LinkedIn
    if CREDENTIALS["linkedin"]["email"]:
         tasks.append(pool.apply_async(worker, ("linkedin", topic, CREDENTIALS["linkedin"])))
    
    # Tarea Twitter
    if CREDENTIALS["twitter"]["username"]:
        tasks.append(pool.apply_async(worker, ("twitter", topic, CREDENTIALS["twitter"])))
    
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
    
    # Guardar Corpus (CSV)
    filename = f"data/corpus_{topic}.csv"
    
    if len(all_data) > 0:
        # Asumimos que todos los diccionarios tienen las mismas claves (source, type, author, content)
        keys = all_data[0].keys()
        
        try:
            with open(filename, "w", newline='', encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(all_data)
            print(f"\n[Terminado] Se han guardado {len(all_data)} registros en {filename}")
        except Exception as e:
            print(f"\n[Error] No se pudo guardar el CSV: {e}")
    else:
        print("\n[Terminado] No se encontraron datos para guardar.")
