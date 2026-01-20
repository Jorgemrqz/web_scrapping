from playwright.sync_api import sync_playwright
import time
import random
import os

def scrape_linkedin(topic, email, password):
    print(f"[LinkedIn] Iniciando extracción para el tema: {topic}")
    
    # Directorio para guardar sesión (cookies, etc.) al igual que en FB
    user_data_dir = "auth_profile_linkedin"
    
    # Resultados
    results = []
    
    # Argumentos para evitar detección (similares a FB)
    args_list = [
        "--disable-blink-features=AutomationControlled",
        "--start-maximized",
        "--disable-infobars",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu",
    ]

    with sync_playwright() as p:
        try:
            # Usamos contexto persistente
            browser = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False, # LinkedIn requiere ver para creer (y resolver captchas)
                args=args_list,
                viewport=None,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        except Exception as e:
            print(f"[LinkedIn] Error lanzando navegador: {e}")
            return []
            
        try:
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            # 1. Navegación inicial y Login
            print("[LinkedIn] Entrando a LinkedIn...")
            page.goto("https://www.linkedin.com/")
            time.sleep(random.uniform(4, 7))
            
            # Verificar si ya estamos logueados (buscando la barra de búsqueda global)
            if page.locator("input[placeholder*='Buscar']").count() > 0 or "feed" in page.url:
                print("[LinkedIn] Sesión detectada. Saltando login.")
            else:
                # Intentar login
                if page.locator("#session_key").count() > 0:
                    print("[LinkedIn] Introduciendo credenciales...")
                    page.fill("#session_key", email)
                    time.sleep(1)
                    page.fill("#session_password", password)
                    time.sleep(1)
                    page.click("button[type='submit']")
                    print("[LinkedIn] Login enviado. Esperando carga...")
                    time.sleep(10) # Espera larga para posibles verificaciones/captchas
                    
                    # Chequeo rápido de si pide PIN o Captcha
                    if "challenge" in page.url:
                        print("[LinkedIn] ! SE REQUIERE VERIFICACIÓN MANUAL (Captcha/PIN) !")
                        print("[LinkedIn] Tienes 30 segundos para resolverlo en la ventana abierta...")
                        time.sleep(30)
            
            # 2. Búsqueda de contenido
            print(f"[LinkedIn] Buscando publicaciones sobre: '{topic}'...")
            query = topic.replace(" ", "%20")
            # Buscar "Publicaciones" (Content) filtrado por fecha si se quisiera, aquí general
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={query}"
            
            page.goto(search_url)
            time.sleep(5)
            
            # 3. Scroll y Recolección
            TARGET_POSTS = 10
            extracted_posts = 0
            
            print("[LinkedIn] Haciendo scroll para cargar resultados...")
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                time.sleep(3)
                
            # Selectores de posts (LinkedIn cambia clases dinámicamente, usaremos atributos estables si es posible)
            # Contenedor principal de cada update: div.update-components-actor es el header
            # El contenedor del post suele tener data-urn="..."
            
            container_selector = "li.reusable-search__result-container"
            posts = page.locator(container_selector)
            count = posts.count()
            print(f"[LinkedIn] Encontrados {count} posts visibles.")
            
            for i in range(min(count, TARGET_POSTS)):
                print(f"\n[LinkedIn] --- Procesando Post {i+1} ---")
                post = posts.nth(i)
                post.scroll_into_view_if_needed()
                time.sleep(1)
                
                # Extraer Autor
                try:
                     # Usamos selectores genéricos visuales
                     author_el = post.locator("span.update-components-actor__title span.visually-hidden").first
                     if author_el.count() == 0:
                         # Intento alternativo
                         author_el = post.locator("span[dir='ltr']").first
                     
                     author = author_el.inner_text().strip() if author_el.count() > 0 else "Desconocido"
                except:
                     author = "Error Autor"
                
                # Extraer Texto del Post
                try:
                    # El texto suele estar en un span class="break-words"
                    text_el = post.locator("div.update-components-text span.break-words span[dir='ltr']").first
                    content = text_el.inner_text().strip() if text_el.count() > 0 else ""
                except:
                    content = ""
                    
                # Si no hay contenido visible, quizás hay que dar a "ver más"
                if not content:
                     try:
                         see_more = post.locator("button.update-components-text__see-more").first
                         if see_more.count() > 0:
                             see_more.click()
                             time.sleep(1)
                             text_el = post.locator("div.update-components-text span[dir='ltr']").first
                             content = text_el.inner_text().strip()
                     except:
                         pass

                # Guardar Post
                if content:
                    print(f"  [Post] Autor: {author} | Texto: {content[:30]}...")
                    results.append({
                        "source": "LinkedIn",
                        "type": "post",
                        "author": author,
                        "content": content
                    })
                
                # Extraer Comentarios (Solo si los hay visibles o botón)
                # LinkedIn requiere clic en "Comentarios"
                try:
                    # Botón "Comentar" o contador de comentarios
                    # button[aria-label*="comentar"]
                    # Pero en resultados de búsqueda, a veces NO deja ver comentarios sin entrar al post.
                    # En la vista de lista "Content", los posts suelen ser interactivos.
                    
                    # Intentamos ver si hay botón de comentarios
                    comment_btn = post.locator("button[aria-label*='comentario']").first
                    if comment_btn.count() > 0:
                        comment_btn.click()
                        time.sleep(2)
                        
                        # Ahora buscamos los comentarios cargados
                        # class comments-comment-item
                        comments = post.locator("article.comments-comment-item")
                        c_count = comments.count()
                        if c_count > 0:
                            print(f"  [Comentarios] Encontrados {c_count}.")
                            for j in range(min(c_count, 5)): # Max 5 comentarios por post
                                c_item = comments.nth(j)
                                try:
                                    c_auth_el = c_item.locator("span.comments-post-meta__name-text").first
                                    c_auth = c_auth_el.inner_text().strip() if c_auth_el.count() > 0 else "Anónimo"
                                except:
                                    c_auth = "Anónimo"
                                
                                try:
                                    c_text_el = c_item.locator("div.comments-comment-item__main-content").first
                                    c_text = c_text_el.inner_text().strip() if c_text_el.count() > 0 else ""
                                except:
                                    c_text = ""
                                
                                if c_text:
                                    results.append({
                                        "source": "LinkedIn",
                                        "type": "comment",
                                        "author": c_auth,
                                        "content": c_text
                                    })
                except Exception as e:
                    # print(f"  [Debug] No se pudieron extraer comentarios: {e}")
                    pass
            
            print(f"[LinkedIn] Finalizado. {len(results)} elementos extraídos.")
            
        except Exception as e:
            print(f"[LinkedIn] Error fatal: {e}")
        finally:
            try:
                browser.close()
            except:
                pass
                
    return results
