import sys
import os
# Añadir el directorio raíz al path para importar scrapers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.linkedin import scrape_linkedin
from config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD

if __name__ == "__main__":
    print("--- TEST INDIVIDUAL DE LINKEDIN ---")
    topic = input("Tema a buscar [Enter='Ecuador']: ") or "Ecuador"
    
    # Ejecutar solo la función de LinkedIn
    results = scrape_linkedin(topic, LINKEDIN_EMAIL, LINKEDIN_PASSWORD, target_count=3)
    
    print("\n--- RESULTADOS ---")
    for r in results:
        print(f"Autor: {r['author']}")
        print(f"Texto: {r['content'][:100]}...")
        print("-" * 20)
