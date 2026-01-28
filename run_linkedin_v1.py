import sys
import os

# Asegurar que podemos importar desde el directorio actual
sys.path.append(os.getcwd())

from scrapers.linkedin_v1 import scrape_linkedin
from config import CREDENTIALS, DEFAULT_TOPIC

def main():
    print("--- Iniciando Ejecución Aislada de LinkedIn V1 ---")
    
    # Obtener credenciales
    li_creds = CREDENTIALS.get("linkedin", {})
    email = li_creds.get("email")
    password = li_creds.get("password")
    
    if not email or not password:
        print("Error: No hay credenciales de LinkedIn configuradas en config.py")
        return

    # Tema por defecto o input manual
    topic = DEFAULT_TOPIC if DEFAULT_TOPIC else "Venezuela" # Fallback
    
    print(f"Tema: {topic}")
    print("Iniciando scraper...")
    
    # Ejecutar función importada
    results = scrape_linkedin(topic, email, password, target_count=5) # Probamos con 5 items para test rápido
    
    print("\n--- Resultados Obtenidos ---")
    if results:
        import pandas as pd
        df = pd.DataFrame(results)
        output_csv = "test_linkedin_v1.csv"
        df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"Resultados guardados en: {output_csv}")
    
    for i, res in enumerate(results):
        p_auth = res.get('post_author', 'N/A')
        print(f"[{i+1}] LinkedIn | Post Autor: {p_auth}")
        # Mostrar post o comentario según corresponda
        txt = res.get('comment_content') if res.get('comment_content') else res.get('post_content', '')
        print(f"    Contenido: {txt[:100]}...")
        print("-" * 20)

if __name__ == "__main__":
    main()
