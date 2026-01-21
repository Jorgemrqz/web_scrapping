import os
import time
import random
import re
from playwright.sync_api import sync_playwright

def human_delay(min_s=1, max_s=3):
    time.sleep(random.uniform(min_s, max_s))

def scrape_linkedin(topic, email, password, target_count=10):
    results = []
    print(f"[LinkedIn] Iniciando modo 'Humano' (Reversa + Comentarios) para: {topic} | Meta: {target_count}")
    
    user_data_dir = os.path.join(os.getcwd(), "auth_profile_linkedin")
    
    # User Agent estándar
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    with sync_playwright() as p:
        print(f"[LinkedIn] Usando perfil en: {user_data_dir}")
        
        args_list = [
            "--disable-notifications",
            "--disable-blink-features=AutomationControlled", 
            "--start-maximized",
            "--no-sandbox",
            "--disable-gpu"
        ]
        
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=args_list,
                user_agent=user_agent,
                viewport=None
            )
        except Exception as launch_error:
            print(f"[LinkedIn] Error lanzando navegador: {launch_error}")
            return []
        
        if len(browser.pages) > 0:
            page = browser.pages[0]
        else:
            page = browser.new_page()
            
        page.set_default_timeout(30000)

        try:
            # 1. Login / Verificación
            try:
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                human_delay(2, 3)
            except Exception as e:
                pass
            
            if "login" in page.url or "guest" in page.url:
                if email and password:
                     try:
                        if page.locator("#username").is_visible():
                            page.fill("#username", email)
                            page.fill("#password", password)
                            page.click("button[type='submit']")
                            page.wait_for_timeout(5000)
                     except:
                        pass

            # 2. Búsqueda
            print(f"[LinkedIn] Buscando: '{topic}'...")
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={topic}&origin=GLOBAL_SEARCH_HEADER"
            
            page.goto(search_url, wait_until="domcontentloaded")
            time.sleep(5)
            
            processed_ids = set()
            scroll_attempts_without_new = 0
            
            while len(results) < target_count and scroll_attempts_without_new < 5:
                
                print(f"[LinkedIn] Escaneando posts... (Llevamos {len(results)})")
                
                # ESTRATEGIA REVERSA: Buscar botones de acción
                action_buttons = page.locator('button')
                candidates = []
                count = action_buttons.count()
                
                found_posts_in_view = []
                
                # Iterar botones para encontrar dueños (Posts)
                for i in range(count):
                    if len(found_posts_in_view) > 5: break 
                    try:
                        btn = action_buttons.nth(i)
                        txt = btn.inner_text().lower()
                        aria = (btn.get_attribute("aria-label") or "").lower()
                        
                        if "recomendar" in txt or "comentar" in txt or "recomendar" in aria or "comentar" in aria:
                            if btn.is_visible():
                                parent = btn
                                for _ in range(6):
                                    parent = parent.locator("..")
                                    # Verificar si es un contenedor de post válido (tiene texto)
                                    if parent.inner_text().count("\n") > 3:
                                        found_posts_in_view.append(parent)
                                        break
                    except:
                        continue

                new_in_pass = 0
                print(f"[LinkedIn] Detectados {len(found_posts_in_view)} posts en pantalla.")

                for post_item in found_posts_in_view:
                    if len(results) >= target_count: break
                    
                    try:
                        # Scroll para trabajar
                        post_item.scroll_into_view_if_needed()
                        human_delay(0.5, 1)
                        
                        text_content = post_item.inner_text()
                        post_hash = hash(text_content[:50])
                        
                        if post_hash in processed_ids: continue
                        processed_ids.add(post_hash)
                        
                        # A) Extraer Post Principal
                        clean_content = text_content.replace("\n", " ").strip()
                        clean_content = clean_content.split("Recomendar Comentar")[0] # Limpia
                        
                        author = "Desconocido"
                        # Intento de autor mejorado
                        try:
                            lines = text_content.split("\n")
                            # Heurística: Las primeras líneas suelen tener el nombre o "Publicación de..."
                            for l in lines[:5]:
                                if len(l) > 2 and "Publicación" not in l and "seguidores" not in l:
                                    author = l.strip()
                                    break
                        except: pass

                        results.append({
                            "source": "LinkedIn", "type": "post",
                            "author": author, "content": clean_content
                        })
                        new_in_pass += 1
                        print(f"[LinkedIn] > Post capturado (Autor: {author})")

                        # B) Extraer Comentarios
                        # Buscar botón que diga "X comentarios" para abrirlo
                        try:
                            # Regex para buscar "5 comentarios", "1 comentario"
                            comment_trigger = post_item.locator('button, span, a').filter(has_text=re.compile(r"\d+\s+comentario", re.IGNORECASE)).first
                            if comment_trigger.count() > 0:
                                print("   [LinkedIn] Abriendo comentarios...")
                                comment_trigger.click()
                                time.sleep(2)
                                
                                # Buscar contenedores de comentarios (suelen ser article o div con clase comments-comment-item)
                                comments_list = post_item.locator('article.comments-comment-item, div.comments-comment-item')
                                c_count = comments_list.count()
                                print(f"   [LinkedIn] {c_count} comentarios visibles.")
                                
                                for j in range(c_count):
                                    c_el = comments_list.nth(j)
                                    c_text = c_el.inner_text().replace("\n", " ").strip()
                                    
                                    # Limpiar un poco (quitar nombre autor del texto si se repite)
                                    # Esto es básico, se puede mejorar
                                    if len(c_text) > 5:
                                        results.append({
                                            "source": "LinkedIn", "type": "comment",
                                            "author": "Usuario LinkedIn", # Difícil sacar exacto sin selectores complejos
                                            "content": c_text
                                        })
                                        # print(f"     -> Comentario extraído: {c_text[:30]}...")
                                        
                        except Exception as e:
                            # print(f"   [LinkedIn] No se pudieron sacar comentarios: {e}")
                            pass

                    except Exception as e:
                        pass
                        
                if new_in_pass == 0:
                    scroll_attempts_without_new += 1
                    print("[LinkedIn] Bajando más...")
                    page.keyboard.press("End") 
                    time.sleep(2)
                else:
                    scroll_attempts_without_new = 0
                    print("[LinkedIn] Siguiente bloque...")
                    page.mouse.wheel(0, 600)
                    time.sleep(1)
                    
                # Paginación
                try:
                    next_btn = page.locator('button.artdeco-pagination__button--next')
                    if next_btn.count() > 0 and next_btn.is_visible() and scroll_attempts_without_new > 2:
                        next_btn.click()
                        time.sleep(4)
                        scroll_attempts_without_new = 0
                except: pass

            print(f"[LinkedIn] Finalizado. Total: {len(results)}")
            
        except Exception as e:
            print(f"[LinkedIn] Error Global: {e}")
        finally:
            try: browser.close()
            except: pass
                
    return results
