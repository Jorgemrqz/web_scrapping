import csv
import os
import config
from scrapers.facebook import scrape_facebook

def main():
    # 1. Configuración
    email = config.FB_EMAIL
    password = config.FB_PASSWORD
    topic = config.DEFAULT_TOPIC or input("Tema a buscar: ")
    
    # Preguntar cantidad (opcional, por defecto 10)
    try:
        limit_input = input(f"Cantidad de posts a buscar [Default=10]: ")
        target_count = int(limit_input) if limit_input.strip() else 10
    except:
        target_count = 10

    print(f"\n--- Iniciando Scraper de Facebook Solo ---")
    print(f"Tema: {topic}")
    print(f"Meta: {target_count} posts")
    
    # 2. Ejecutar Scraper
    # Nota: scrape_facebook ya maneja su propio navegador
    results = scrape_facebook(topic, email, password, target_count=target_count)
    
    # 3. Guardar Resultados
    if results:
        # Asegurar directorio data
        os.makedirs("data", exist_ok=True)
        
        filename = f"data/facebook_{topic.replace(' ', '_')}.csv"
        
        # Obtener claves para el CSV (usando el primer resultado como referencia)
        # Aseguramos que 'post_author' y 'post_content' estén si existen, si no las claves estándar
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
