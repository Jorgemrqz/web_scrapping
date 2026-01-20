from playwright.sync_api import sync_playwright
import os

def manual_login():
    # Ruta IMPORTANTE: Coincidir con el script principal
    user_data_dir = os.path.join(os.getcwd(), "auth_profile")
    
    # Asegurar que existe
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    
    print(f"Abriendo CHROMIUM en modo manual con perfil: {user_data_dir}")
    print("Por favor, inicia sesión. Si se cierra solo, hay un problema de librería.")

    with sync_playwright() as p:
        # Lanzamos CHROMIUM (por defecto de playwright, más estable)
        browser = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            # channel="chrome",  <-- Quitamos esto para usar el Chromium integrado
            args=["--start-maximized", "--no-sandbox", "--disable-gpu"],
            viewport=None
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://www.facebook.com/")
        
        # Mantenemos el script vivo hasta que tú cierres el navegador
        try:
            page.wait_for_timeout(9999999) # Esperar indefinidamente
        except:
            print("Navegador cerrado. Sesión guardada (si iniciaste correctamente).")

if __name__ == "__main__":
    manual_login()
