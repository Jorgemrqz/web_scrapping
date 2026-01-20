import multiprocessing
import json
import os
from scrapers.facebook import scrape_facebook
from scrapers.twitter import scrape_twitter

import config

# Configuración (En un caso real, usar variables de entorno)
CREDENTIALS = {
    "facebook": {"email": "", "password": ""},
    "twitter": {"username": "", "password": ""},
}

def worker(platform, topic, creds):
    """ Función wrapper para el proceso paralelo """
    print(f"--- Iniciando Worker: {platform} ---")
    data = []
    
    if platform == "facebook":
        data = scrape_facebook(topic, creds['email'], creds['password'])
    elif platform == "twitter":
        # Simulación o llamada real si tenemos credenciales
        if creds['username']:
            data = scrape_twitter(topic, creds['username'], creds['password'])
        else:
            print(f"[{platform}] Salteando (sin credenciales)")
    
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
        print(f"[Config] Credenciales Facebook cargadas para: {config.FB_EMAIL}")
    else:
        print("\n--- Credenciales Facebook ---")
        CREDENTIALS["facebook"]["email"] = input("Email: ")
        CREDENTIALS["facebook"]["password"] = input("Password: ")
    
    # 3. Configurar TWITTER/X
    if config.X_USER:
         CREDENTIALS["twitter"]["username"] = config.X_USER
         CREDENTIALS["twitter"]["password"] = config.X_PASSWORD
         print(f"[Config] Credenciales X cargadas para: {config.X_USER}")
    else:
        # Si no hay en config, preguntamos pero permitimos saltar
        pass # Por ahora asumimos que si no está en config, no se quiere usar o se deja vacío

    print("\n[Orquestador] Iniciando extracción PARALELA...")
    
    # Crear procesos
    # Usamos multiprocessing para cumplir con el requisito académico
    pool = multiprocessing.Pool(processes=2) # Número de redes a scrapear
    
    tasks = []
    # Tarea Facebook
    tasks.append(pool.apply_async(worker, ("facebook", topic, CREDENTIALS["facebook"])))
    
    # Tarea Twitter (si hay user)
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
    
    # Guardar Corpus
    filename = f"data/corpus_{topic}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n[Terminado] Se han guardado {len(all_data)} registros en {filename}")
