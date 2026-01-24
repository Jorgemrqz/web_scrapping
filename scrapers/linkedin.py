import os
import time
import random
import re
from playwright.sync_api import sync_playwright

def human_delay(min_s=1, max_s=3):
    time.sleep(random.uniform(min_s, max_s))

def scrape_linkedin(topic, email, password, target_count=10):
    results = []
    print(f"[LinkedIn] Modo 'Humano' (Diferencia de Texto) para: {topic} | Meta: {target_count}")
    
    user_data_dir = os.path.join(os.getcwd(), "auth_profile_linkedin")
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    with sync_playwright() as p:
        print(f"[LinkedIn] Usando perfil en: {user_data_dir}")
        args_list = ["--disable-notifications", "--disable-blink-features=AutomationControlled", "--start-maximized", "--no-sandbox", "--disable-gpu"]
        
        try:
            browser = p.chromium.launch_persistent_context(user_data_dir, headless=False, args=args_list, user_agent=user_agent, viewport=None)
        except Exception as launch_error:
            print(f"[LinkedIn] Error lanzando navegador: {launch_error}")
            return []
        
        if len(browser.pages) > 0: page = browser.pages[0]
        else: page = browser.new_page()
        page.set_default_timeout(30000)

        try:
            # Login check
            try: page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded"); human_delay(2,3)
            except: pass
            if "login" in page.url:
                 if email and password and page.locator("#username").is_visible():
                    page.fill("#username", email); page.fill("#password", password); page.click("button[type='submit']"); page.wait_for_timeout(5000)

            print(f"[LinkedIn] Buscando: '{topic}'...")
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={topic}&origin=SWITCH_SEARCH_VERTICAL"
            page.goto(search_url, wait_until="domcontentloaded")
            time.sleep(5)
            
            processed_ids = set()
            scroll_attempts_without_new = 0
            
            while len(results) < target_count and scroll_attempts_without_new < 8:
                
                print(f"[LinkedIn] Escaneando... (Rec: {len(results)})")
                
                found_posts = []
                # Filtro regex estricto para boton acción
                action_btns = page.locator('button').filter(has_text=re.compile(r"^comentar$|^comment$", re.IGNORECASE))
                
                count = action_btns.count()
                for i in range(count):
                    if len(found_posts) > 6: break
                    try:
                        b = action_btns.nth(i)
                        if b.is_visible():
                            # Subir al post container
                            p_cont = b
                            for _ in range(4): 
                                p_cont = p_cont.locator("..")
                                if p_cont.inner_text().count("\n") > 3: 
                                    found_posts.append((p_cont, b)) # Guardamos par (Post, Botón)
                                    break
                    except: continue

                new_in_pass = 0
                for post_item, action_btn in found_posts:
                    if len(results) >= target_count: break
                    try:
                        post_item.scroll_into_view_if_needed()
                        human_delay(0.5, 1)
                        
                        # --- CAPTURA TEXTO ANTES (MOMENTO A) ---
                        txt_before = post_item.inner_text()
                        
                        phash = hash(txt_before[:50])
                        if phash in processed_ids: continue
                        processed_ids.add(phash)
                        
                        # -- Autor y Post --
                        lines = txt_before.split('\n')
                        author = "Desconocido"
                        for l in lines:
                            l = l.strip()
                            if len(l) > 2 and "Publicación" not in l and "seguidores" not in l and "minutos" not in l:
                                author = l
                                break
                        
                        post_clean = txt_before.split("Recomendar")[0].replace("\n", " ").strip()
                        
                        results.append({
                            "source": "LinkedIn", "type": "post", 
                            "author": author[:50], 
                            "content": post_clean
                        })
                        new_in_pass += 1
                        print(f"[LinkedIn] > Post: {author[:20]}")

                        # -- CLIC AL BOTÓN DE ACCIÓN 'COMENTAR' --
                        print(f"   [LinkedIn] Clic botón Comentar (Diff)...")
                        try:
                            action_btn.click(force=True)
                            time.sleep(3) # Esperar despliegue (IMPORTANTE)
                        except: pass

                        # --- CAPTURA TEXTO DESPUES (MOMENTO B) ---
                        txt_after = post_item.inner_text()
                        
                        # --- ESTRATEGIA DIFERENCIA DE TEXTO ---
                        # Si B > A, lo nuevo son comentarios
                        
                        lines_A = set([l.strip() for l in txt_before.split('\n') if len(l.strip())>0])
                        lines_B = [l.strip() for l in txt_after.split('\n') if len(l.strip())>0]
                        
                        c_extracted = 0
                        bad_tokens = ["Publicación en el feed", "Recomendar", "Comentar", "Compartir", "Enviar", author, "seguidores", "ver más", "Responder"]
                        
                        for line in lines_B:
                            if line not in lines_A:
                                # Es texto NUEVO -> Posible comentario
                                c_txt = line
                                if len(c_txt) > 3 and len(c_txt) < 600:
                                    # Filtros
                                    if author in c_txt: continue
                                    if post_clean[:20] in c_txt: continue
                                    
                                    is_garbage = False
                                    for bad in bad_tokens:
                                        if bad.lower() in c_txt.lower(): is_garbage=True
                                    if is_garbage: continue
                                    
                                    is_dup = False
                                    for r in results[-10:]:
                                        if r['content'] == (c_txt.replace("\n", " ")): is_dup = True
                                    
                                    if not is_dup:
                                        results.append({
                                            "source": "LinkedIn", "type": "comment",
                                            "author": "Usuario LinkedIn",
                                            "content": c_txt.replace("\n", " ")
                                        })
                                        c_extracted += 1
                                        if c_extracted >= 5: break
                        
                        if c_extracted > 0:
                            print(f"   [LinkedIn] -> {c_extracted} comentarios extraídos (Diff Strategy).")

                    except Exception: pass
                        
                if new_in_pass == 0:
                    scroll_attempts_without_new += 1
                    page.keyboard.press("End") 
                    time.sleep(2)
                else:
                    scroll_attempts_without_new = 0
                    page.mouse.wheel(0, 500)
                    time.sleep(1)

                try:
                    if scroll_attempts_without_new > 2:
                        page.locator('button.artdeco-pagination__button--next').click()
                        time.sleep(3); scroll_attempts_without_new=0
                except: pass

            print(f"[LinkedIn] Finalizado. Total: {len(results)}")
            
        except Exception as e:
            print(f"[LinkedIn] Error Global: {e}")
        finally:
            try: browser.close()
            except: pass
                
    return results
