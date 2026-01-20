from playwright.sync_api import sync_playwright
import time
import os
import random

import re

def scrape_facebook(topic, email, password):
    results = []
    print(f"[Facebook] Iniciando hilo para: {topic}")
    
    # Ruta para guardar el perfil de usuario (cookies, cache, etc)
    user_data_dir = os.path.join(os.getcwd(), "auth_profile")
    
    with sync_playwright() as p:
        # Usar contexto persistente para guardar la sesión
        print(f"[Facebook] Usando perfil en: {user_data_dir}")
        
        # Argumentos para parecer un navegador real (evadir detección básica)
        args_list = [
            "--disable-notifications",
            "--disable-blink-features=AutomationControlled", 
            "--start-maximized",
            "--no-sandbox",
            "--disable-gpu"
        ]
        
        # Intentar lanzar con manejo de errores de lock
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                args=args_list,
                locale='es-ES',
                viewport=None
            )
        except Exception as launch_error:
            print(f"[Facebook] Error lanzando navegador: {launch_error}")
            print("[Facebook] Posiblemente el perfil está bloqueado. Intenta cerrar todos los procesos de Chrome.")
            return []
        
        # En contexto persistente, browser actúa como context y tiene pages
        if len(browser.pages) > 0:
            page = browser.pages[0]
        else:
            page = browser.new_page()

        try:
            # 1. Login
            page.goto("https://www.facebook.com/")
            time.sleep(random.uniform(3, 5))
            
            # Verificar si ya estamos logueados (cookies) o hay que loguear
            if page.locator("input[name='email']").count() > 0:
                print(f"[Facebook] Introduciendo email...")
                page.fill("input[name='email']", email)
                time.sleep(random.uniform(2, 4))
                
                print(f"[Facebook] Introduciendo password...")
                page.fill("input[name='pass']", password)
                time.sleep(random.uniform(2, 4))
                
                print(f"[Facebook] Click en Login...")
                page.click("button[name='login']")
                
                # Esperar a que Facebook termine de redirigir
                print("[Facebook] Esperando a que cargue el inicio...")
                login_success = False
                for i in range(20): # Esperar hasta 60s
                    time.sleep(3)
                    # Detectar feed, banner, o presencia de historias (div[aria-label='Historias'])
                    if (page.locator('div[role="feed"]').count() > 0 or 
                        page.locator('div[role="banner"]').count() > 0 or
                        page.locator('div[aria-label="Historias"]').count() > 0):
                        print("[Facebook] ¡Inicio detectado correctamente!")
                        login_success = True
                        break
                    
                    # Chequeo url
                    if "facebook.com" in page.url and "login" not in page.url and "checkpoint" not in page.url and i > 5:
                         print("[Facebook] URL parece correcta, asumiendo login exitoso...")
                         login_success = True
                         break

                    if "checkpoint" in page.url or "two_step_verification" in page.url:
                        print("\n[Facebook] !!! ALERTA DE 2FA DETECTADA !!!")
                        print("[Facebook] Por favor, aprueba el acceso o escribe el código en el navegador.")
                        print("[Facebook] Esperando hasta 90 segundos...")
                        time.sleep(90)
                        break
            else:
                 print("[Facebook] Parece que ya hay una sesión iniciada (cookies detectadas).")
                 time.sleep(3)

            # Verificación final de seguridad antes de buscar
            if page.locator("input[name='email']").count() > 0 and "search" not in page.url:
                 print("[Facebook] ADVERTENCIA: Parece que seguimos en el login. El script podría fallar.")
            
            # 2. Búsqueda
            print(f"[Facebook] Navegando a la búsqueda: '{topic}'...")
            
            # Usar try-except para la navegación por si Facebook interrumpe con otra redirección
            try:
                page.goto(f"https://www.facebook.com/search/posts/?q={topic}", wait_until="domcontentloaded")
            except Exception as nav_err:
                print(f"[Facebook] Redirección detectada, reintentando ir a búsqueda... ({nav_err})")
                time.sleep(5)
                page.goto(f"https://www.facebook.com/search/posts/?q={topic}", wait_until="domcontentloaded")
                
            print("[Facebook] Esperando carga de resultados...")
            time.sleep(10)

            
            # 3. Extracción (Posts + Comentarios)
            print("[Facebook] Buscando posts para extraer...")
            
            # ESTRATEGIA: Buscar DENTRO del feed para evitar barras de navegación/notificaciones
            feed = page.locator('div[role="feed"]')
            
            # Si no encuentra feed, buscar en "main" (común en resultados de búsqueda)
            if feed.count() == 0:
                feed = page.locator('div[role="main"]')
            
            if feed.count() > 0:
                print("[Facebook] Contenedor de posts (Feed/Main) detectado.")
                # INTENTO 1: Buscar por rol de artículo
                posts = feed.locator('div[role="article"]')
                
                # INTENTO 2: Buscar por posición en la lista (aria-posinset) -> CRÍTICO para tu caso
                if posts.count() == 0:
                    print("[Facebook] 'role=article' no encontrado. Probando selector 'aria-posinset'...")
                    posts = feed.locator('div[aria-posinset]')
            else:
                print("[Facebook] Contenedor no detectado explícitamente. Buscando articles en toda la página (con cuidado)...")
                posts = page.locator('div[role="article"]')
                if posts.count() == 0:
                    posts = page.locator('div[aria-posinset]')
            
            # Filtrar posts visibles y de tamaño razonable (evitar iconitos ocultos)
            # No podemos filtrar por visible fácilmente sin iterar, así que confiamos en el feed.
            
            if posts.count() == 0:
                 print("[Facebook] Selector principal falló, intentando alternativos...")
                 # Alternativas comunes en FB
                 posts = page.locator('div[data-ad-preview="message"]').locator("..").locator("..").locator("..")
            
            # === Scroll Infinito Controlado ===
            TARGET_POSTS = 25
            print(f"[Facebook] Objetivo: Obtener al menos {TARGET_POSTS} posts...")
            
            scroll_attempts = 0
            max_scrolls = 10 # Seguridad
            
            while posts.count() < TARGET_POSTS and scroll_attempts < max_scrolls:
                print(f"[Facebook] Scroll {scroll_attempts+1}/{max_scrolls} (Posts actuales: {posts.count()})...")
                page.mouse.wheel(0, 4000) # Scroll largo
                time.sleep(4) # Esperar a que cargue contenido
                
                # Re-seleccionar posts para actualizar conteo
                if feed.count() > 0:
                    posts = feed.locator('div[role="article"]')
                    if posts.count() == 0:
                        posts = feed.locator('div[aria-posinset]')
                else:
                    posts = page.locator('div[role="article"]')
                    if posts.count() == 0:
                         posts = page.locator('div[aria-posinset]')
                
                scroll_attempts += 1
                
            count = posts.count()
            print(f"[Facebook] Se encontraron {count} posts tras el scroll.")
            
            # Limitar a los que pidió el usuario
            process_limit = min(count, TARGET_POSTS)
            
            # Iterar sobre los posts requeridos
            for i in range(process_limit):
                print(f"\n[Facebook] --- Procesando Post {i+1} de {count} ---")
                
                # Re-localizar posts en cada iteración por si el DOM cambió (Lógica robusta)
                if i > 0:
                    try:
                        # 1. Buscar Feed o Main
                        feed = page.locator('div[role="feed"]')
                        if feed.count() == 0:
                            feed = page.locator('div[role="main"]')
                        
                        # 2. Buscar Posts (Article o Posinset)
                        if feed.count() > 0:
                            posts = feed.locator('div[role="article"]')
                            if posts.count() == 0:
                                posts = feed.locator('div[aria-posinset]')
                        else:
                            posts = page.locator('div[role="article"]')
                            if posts.count() == 0:
                                posts = page.locator('div[aria-posinset]')
                    except Exception as e:
                        print(f"[Facebook] Error re-localizando posts: {e}")
                
                if i >= posts.count():
                    print("[Facebook] Fin de la lista de posts.")
                    break
                    
                post_body = posts.nth(i)
                first_post = post_body 
                
                # Scroll al post para asegurar visibilidad
                try:
                    first_post.scroll_into_view_if_needed()
                    time.sleep(1)
                except:
                    pass

                try:
                    candidate = post_body
                    found_parent = False
                    for _ in range(5): 
                        candidate = candidate.locator("..")
                        if candidate.filter(has_text="Comentar").count() > 0:
                            first_post = candidate
                            found_parent = True
                            break
                except:
                   pass

                # ESTRATEGIA: Buscar botón de "X comentarios"
                print("[Facebook] Buscando botón de recuento de comentarios...")
                clicked = False
                
                try:
                    # Regex para "100 comentarios", "1 comentario", etc.
                    comment_count_btn = first_post.locator('div[role="button"], span[role="button"]').filter(has_text=re.compile(r"\d+\s+comentarios?", re.IGNORECASE)).first
                    
                    if comment_count_btn.count() > 0:
                        print("[Facebook] Botón de recuento de comentarios encontrado. Click...")
                        comment_count_btn.click(force=True)
                        clicked = True
                    else:
                        # Si no hay contador, buscamos texto "Comentar"
                        comentar_btn = first_post.locator('div[role="button"], span[role="button"]').filter(has_text="Comentar").first
                        if comentar_btn.count() > 0:
                             print("[Facebook] Botón 'Comentar' encontrado. Click...")
                             comentar_btn.click(force=True)
                             clicked = True

                except Exception as e:
                    print(f"[Facebook] Error click comentarios: {e}")

                # Fallback: Ancla en "Me gusta"
                if not clicked:
                    print("[Facebook] Fallback: Usando 'Me gusta' como ancla...")
                    try:
                        # Buscamos el botón 'Me gusta' (reacciones)
                        like_btn = first_post.locator('div[aria-label^="Me gusta"], div[aria-label^="Reaccionar"]').first
                        if like_btn.count() > 0:
                            box = like_btn.bounding_box()
                            if box:
                                # Click 80 px ARRIBA del botón Like. 
                                target_x = box["x"] + (box["width"] / 2)
                                target_y = box["y"] - 60 
                                print(f"[Facebook] Click en coordenadas del cuerpo: {target_x}, {target_y}")
                                page.mouse.click(target_x, target_y)
                                clicked = True
                    except Exception as e:
                         print(f"[Facebook] Error en fallback de ancla: {e}")

                time.sleep(5)
                
                # --- Preparar contenedor para extracción ---
                container = page
                if page.locator('div[role="dialog"]').count() > 0:
                     print("[Facebook] Dialogo modal detectado.")
                     container = page.locator('div[role="dialog"]').last # Usar el último dialogo activo
                     
                     # CHEQUEO DE SEGURIDAD: ¿Es el panel de notificaciones? (Solo si es visible)
                     try:
                         notif_header = container.locator('h1:has-text("Notificaciones")')
                         if notif_header.count() > 0 and notif_header.first.is_visible():
                             print("[Facebook] ¡Panel de notificaciones REALMENTE abierto! Cerrando...")
                             page.keyboard.press("Escape")
                             time.sleep(2)
                             first_post.click(force=True) # Reintentar click simple
                             time.sleep(3)
                             if page.locator('div[role="dialog"]').count() > 0:
                                 container = page.locator('div[role="dialog"]').last
                     except:
                         pass

                     # SOPORTE PARA VÍDEOS: Si hay video, buscar icono de comentarios
                     if container.locator('video').count() > 0 or container.locator('div[aria-label*="Video"]').count() > 0:
                         print("[Facebook] Modal de video detectado. Buscando botón de comentarios...")
                         # Intentar botón de burbuja (común en Facebook Watch)
                         try:
                             # Icono de burbuja o texto "Comentarios"
                             bubble_btn = container.locator('div[aria-label*="Comentario"], div[aria-label*="Comment"], i[data-visualcompletion="css-img"]').filter(has_text=re.compile(r"comentario", re.IGNORECASE))
                             if bubble_btn.count() > 0:
                                 if bubble_btn.first.is_visible():
                                     print("[Facebook] Icono de comentarios de video encontrado. Click...")
                                     bubble_btn.first.click()
                                     time.sleep(2)
                             else:
                                 # Intento genérico en barra lateral derecha
                                 sidebar_comment = container.locator('div[role="button"]:has-text("Comentarios")')
                                 if sidebar_comment.count() > 0 and sidebar_comment.first.is_visible():
                                     sidebar_comment.first.click()
                                     time.sleep(2)
                         except:
                             pass
                
                # --- Extraer Comentarios ---
                
                # Espera activa
                time.sleep(2)
                
                # Selector 1: Específico (Comentario de...)
                comments_loc = container.locator('div[aria-label^="Comentario de"]')
                
                # Selector 2: Genérico (Cualquier artículo en una lista)
                if comments_loc.count() == 0:
                     print("[Facebook] Selector específico falló. Probando genérico...")
                     # Buscamos elementos role="article" que NO sean el post principal
                     # Excluimos el que tenga data-ad-preview="message"
                     comments_loc = container.locator('div[role="article"]')
                
                if comments_loc.count() == 0:
                    print("[Facebook] Selector genérico falló. Probando extracción de texto bruta...")
                    # Estrategia final: Buscar bloques de texto (div[dir="auto"]) que tengan longitud suficiente
                    # y no sean el texto del post original
                    candidate_texts = container.locator('div[dir="auto"]').all()
                    print(f"[Facebook] Se encontraron {len(candidate_texts)} bloques de texto.")
                    
                    extract_count = 0
                    # post_text is not defined in this snippet, assuming it's available from parent scope
                    post_text = "" # Placeholder for post_text if not defined
                    for el in candidate_texts:
                        try:
                            txt = el.inner_text().strip()
                            # Filtros heurísticos:
                            # - Longitud > 3 caracteres
                            # - No es "Me gusta", "Responder", rangos de tiempo cortos
                            # - No igual al post original
                            if len(txt) > 3 and txt not in ["Me gusta", "Responder", "Compartir", "Ver más"] and txt != post_text:
                                # Asumimos autor desconocido
                                results.append({
                                    "source": "Facebook", 
                                    "type": "comment",
                                    "author": "Desconocido (Raw)",
                                    "content": txt
                                })
                                extract_count += 1
                                print(f"  [Debug Raw] Texto encontrado: {txt[:30]}...")
                        except:
                            pass
                    print(f"[Facebook] Extracción finalizada (modo bruto). {extract_count} elementos.")
                    # NO retornamos aquí para permitir seguir con el siguiente post
                    # return results

                c_count = comments_loc.count()
                print(f"[Facebook] {c_count} candidatos a comentarios detectados.")
                
                # Extraemos TODOS
                extract_count = 0
                for i in range(c_count):
                    try:
                        c_el = comments_loc.nth(i)
                        
                        # Autor
                        author = "Anónimo"
                        lbl = c_el.get_attribute("aria-label")
                        if lbl: 
                            author = lbl.replace("Comentario de", "").strip()
                        else:
                            # Intentar sacar autor del link interno
                            author_el = c_el.locator('a[role="link"]').first
                            if author_el.count() > 0:
                                author = author_el.inner_text()

                        # Texto
                        c_text = ""
                        # Buscamos divs con dir="auto"
                        text_divs = c_el.locator('div[dir="auto"]')
                        
                        # Estrategia de texto: concatenar todo lo que no sea el autor
                        found_parts = []
                        if text_divs.count() > 0:
                            for j in range(text_divs.count()):
                                t = text_divs.nth(j).inner_text().strip()
                                # Si no es vacío y no es exactamente el nombre del autor (para evitar ruido)
                                if t and t != author:
                                    found_parts.append(t)
                        
                        if found_parts:
                            c_text = " ".join(found_parts)
                        else:
                             c_text = c_el.inner_text()
                        
                        clean_text = c_text.replace("\n", " ").strip()
                        
                        # --- DEBUG EXTRA ---
                        print(f"  [Debug] Comentario {i}: Autor='{author}' | Texto='{clean_text[:30]}...'")
                        # -------------------

                        # Guardar (Validación simplificada al máximo para debug)
                        if len(clean_text) > 0:
                            results.append({
                                "source": "Facebook", 
                                "type": "comment",
                                "author": author,
                                "content": clean_text
                            })
                            extract_count += 1
                    except Exception as e:
                        print(f"  [Debug] Error extrayendo comentario {i}: {e}")
                        continue
                
                print(f"[Facebook] Extracción finalizada para este post. {extract_count} guardados.")
                
                # CERRAR EL MODAL para poder pasar al siguiente post
                print("[Facebook] Cerrando post actual...")
                page.keyboard.press("Escape")
                time.sleep(2)
                # Doble escape por si acaso (a veces cierra una foto y luego el post)
                page.keyboard.press("Escape")
                time.sleep(2)

            else:
                print("[Facebook] No se encontraron posts visibles.")
                    
        except Exception as e:
            print(f"[Facebook] Error: {e}")
        finally:
            try:
                browser.close()
            except:
                pass
            
    return results
