import os
import sys
import pandas as pd
from scrapers.twitter import scrape_twitter
import config

def main():
    print("--- Iniciando Scraper de Twitter/X Solo ---")
    
    # 1. Obtener Tema
    topic = config.DEFAULT_TOPIC
    if not topic:
        topic = input("Ingresa el tema o hashtag a buscar: ")
    
    if not topic:
        print("[!] Tema vacío. Saliendo.")
        return

    try:
        limit_input = input("Cantidad de POSTS a buscar [Default=5]: ")
        limit = int(limit_input) if limit_input.strip() else 5
    except:
        limit = 5

    print(f"Hashtag/Tema: {topic}")
    print(f"Meta de posts: {limit}")
    
    # 3. Ejecutar Scraper
    data = scrape_twitter(topic, config.X_USER, config.X_PASSWORD, target_count=limit)
    
    # 4. Guardar Resultados
    if data:
        # Asegurar directorio data
        os.makedirs("data", exist_ok=True)
        filename = f"data/twitter_{topic.replace(' ', '_')}.csv"
        
        df = pd.DataFrame(data)
        
        # Reordenar columnas estándar
        cols = ["post_index", "post_author", "post_content", "comment_author", "comment_content"]
        existing_cols = [c for c in cols if c in df.columns]
        # Agregar las que falten al final
        remaining = [c for c in df.columns if c not in cols]
        df = df[existing_cols + remaining]
        
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n[Éxito] Se guardaron {len(df)} registros en '{filename}'")
    else:
        print("\n[!] No se encontraron datos o hubo un error.")

if __name__ == "__main__":
    main()
