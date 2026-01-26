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
            
            # Counter exclusivo de comentarios
            total_comments_extracted = 0
            
            while total_comments_extracted < target_count and scroll_attempts_without_new < 15:
                
                print(f"[LinkedIn] Escaneando... (Comentarios: {total_comments_extracted}/{target_count})")
                
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
                    if total_comments_extracted >= target_count: break
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

                        # -- NUEVA ESTRATEGIA INTEGRADA --
                        
                        # 1. Intentar abrir comentarios (Click en "X comentarios" o "Comentar")
                        comments_opened = False
                        try:
                            # Buscar botón tipo "5 comentarios"
                            count_btn = post_item.locator('button, a, span').filter(has_text=re.compile(r"\d+\s+comentarios?", re.IGNORECASE)).first
                            if count_btn.count() > 0 and count_btn.is_visible():
                                count_btn.click(force=True)
                                comments_opened = True
                                time.sleep(3)
                            else:
                                # Fallback al botón de acción "Comentar"
                                if action_btn.is_visible():
                                    action_btn.click(force=True)
                                    comments_opened = True
                                    time.sleep(3)
                        except: pass
                        
                        # 2. Intentar cargar más comentarios si hay botón "Ver más comentarios"
                        try:
                            more_btns = post_item.locator('button').filter(has_text=re.compile(r"ver más comentarios|load more comments", re.IGNORECASE))
                            if more_btns.count() > 0 and more_btns.first.is_visible():
                                more_btns.first.click(force=True)
                                time.sleep(2)
                        except: pass

                        # 3. Extraer utilizando selectores de comentarios de LinkedIn
                        # Clases típicas: .comments_comment-item, .comments-comments-list__comment-item
                        # O buscar artículos dentro de la sección de comentarios
                        
                        # Buscamos contendores de comentarios DENTRO del post_item para no mezclar
                        # Selectores heurísticos basados en estructura actual (2025/2026 estimación)
                        
                        possible_comments = post_item.locator('article.comments-comment-item, div.comments-comment-item, article.comments-comments-list__comment-item')
                        
                        # Si selectores de clase fallan, buscar por estructura general (bloques de texto y autor)
                        if possible_comments.count() == 0:
                             # Buscar artículos genéricos dentro del post que NO sean el post mismo
                             possible_comments = post_item.locator('article').filter(has_text=re.compile(r"Recomendar|Responder", re.IGNORECASE))
                        
                        c_found_count = possible_comments.count()
                        
                        # Procesar candidatos
                        c_extracted_post = 0
                        for j in range(c_found_count):
                            if total_comments_extracted >= target_count: break
                            if c_extracted_post >= 20: break # Max por post
                            
                            try:
                                comm_el = possible_comments.nth(j)
                                comm_text = comm_el.inner_text().strip()
                                
                                # Limpieza básica
                                # Separar autor de contenido. Suele ser: "Autor\nCargo\nTexto..."
                                lines = [l.strip() for l in comm_text.split('\n') if len(l.strip()) > 1]
                                
                                c_author = "Usuario LinkedIn"
                                c_content = ""
                                
                                # Heurística simple: Linea 1 = Autor, Última linea larga = Contenido
                                if len(lines) >= 2:
                                    c_author = lines[0]
                                    # Juntar resto excluyendo palabras clave de UI "Recomendar Responder..."
                                    clean_lines = []
                                    start_content = False
                                    for line in lines[1:]:
                                        # Filtro de ruido UI
                                        if any(x in line for x in ["Recomendar", "Responder", "Ver traducción", "hace", "meses", "días", "horas", "editado"]):
                                            continue
                                        clean_lines.append(line)
                                    c_content = " ".join(clean_lines)
                                else:
                                    c_content = comm_text
                                    
                                if len(c_content) > 3 and c_content != post_clean:
                                    # Verificar duplicados locales
                                    is_dup = False
                                    for r in results[-10:]:
                                        if r['content'] == c_content: is_dup = True
                                    
                                    if not is_dup:
                                        results.append({
                                            "source": "LinkedIn", "type": "comment",
                                            "author": c_author[:50],
                                            "content": c_content
                                        })
                                        c_extracted_post += 1
                                        total_comments_extracted += 1
                                        
                            except: pass
                            
                        if c_extracted_post > 0:
                            print(f"   [LinkedIn] + {c_extracted_post} comentarios extraídos.")
                        else:
                            pass # print("   [LinkedIn] (Sin comentarios extraíbles)")

                    except Exception as e:
                         # print(f"Err Post: {e}")
                         pass
                        
                if new_in_pass == 0:
                    scroll_attempts_without_new += 1
                    page.keyboard.press("End") 
                    time.sleep(2)
                else:
                    scroll_attempts_without_new = 0
                    page.mouse.wheel(0, 600)
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
