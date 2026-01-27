import csv
import os
import config
from scrapers.instagram import scrape_instagram

def main():
    # 1. Configuración
    topic = config.DEFAULT_TOPIC or input("Hashtag a buscar (sin #): ")
    
    try:
        limit_input = input(f"Cantidad de posts a buscar [Default=5]: ")
        target_count = int(limit_input) if limit_input.strip() else 5
    except:
        target_count = 5

    print(f"\n--- Iniciando Scraper de Instagram Solo ---")
    print(f"Hashtag: #{topic}")
    print(f"Meta: {target_count} posts")
    
    # 2. Ejecutar Scraper
    # Nota: scrape_instagram devuelve lista de dicts
    results = scrape_instagram(topic, "", "", target_count=target_count)
    
    # 3. Guardar Resultados
    if results:
        os.makedirs("data", exist_ok=True)
        filename = f"data/instagram_{topic.replace(' ', '_')}.csv"
        
        # Obtener claves dinámicamente
        keys = results[0].keys()
        
        try:
            with open(filename, "w", newline='', encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(results)
            print(f"\n[Éxito] Se guardaron {len(results)} registros en '{filename}'")
        except Exception as e:
            print(f"\n[Error] No se pudo guardar el archivo: {e}")
    else:
        print("\n[Aviso] No se encontraron datos para guardar.")

if __name__ == "__main__":
    main()
