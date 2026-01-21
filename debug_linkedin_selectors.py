from playwright.sync_api import sync_playwright
import os
import time

def debug_selectors():
    user_data_dir = os.path.join(os.getcwd(), "auth_profile_linkedin")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Verlo en pantalla
            viewport=None
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        print("1. Navegando a búsqueda...")
        page.goto("https://www.linkedin.com/search/results/content/?keywords=inteligencia%20artificial", wait_until="commit")
        
        print("2. Esperando 10 segundos para carga manual...")
        time.sleep(10)
        
        print("3. Analizando estructura...")
        
        # Guardar HTML completo para revisión
        with open("debug_linkedin_dump.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("   -> Guardado 'debug_linkedin_dump.html' (HTML completo)")

        # Probar selectores comunes y contar
        selectors = [
            "li.reusable-search__result-container",
            "div.feed-shared-update-v2",
            "div[data-urn]",
            "main ul li",
            "div.occludable-update"
        ]
        
        print("\n--- TEST DE SELECTORES ---")
        found_any = False
        for s in selectors:
            count = page.locator(s).count()
            print(f"Selector '{s}': {count} elementos encontrados.")
            if count > 0:
                found_any = True
                
        if not found_any:
            print("\n[!] NINGUN SELECTOR FUNCIONÓ. Escribiendo estructura básica de 'main'...")
            # Intentar ver qué HAY en main
            main = page.locator("main")
            if main.count() > 0:
                print(main.inner_html()[:2000]) # Primeros 2000 chars del main
            else:
                print("No se encontró tag <main>.")

        print("\nCierra la ventana para terminar.")
        time.sleep(60) # Dar tiempo al usuario a ver

if __name__ == "__main__":
    debug_selectors()
