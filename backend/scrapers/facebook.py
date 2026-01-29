from playwright.sync_api import sync_playwright
import time
import os
import random

import re

def scrape_facebook(topic, email, password, target_count=10):
    results = []
    print(f"[Facebook] Iniciando hilo para: {topic} | Meta: {target_count}")
    
    # Ruta para guardar el perfil de usuario (cookies, cache, etc)
    user_data_dir = os.path.join(os.getcwd(), "profiles", "auth_profile")
    
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
                headless=False,
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
            # Modificado: El objetivo ahora es COMENTARIOS, no posts.
            # Pero necesitamos posts para sacar comentarios.
            # Estrategia: Obtener un batch inicial de posts, procesar, y si falta, scrollear más.
            
            posts_scraped = 0
            collected_comments_count = 0 
            processed_posts_indices = set()
            
            scroll_attempts = 0
            max_scrolls_total = 50 # Aumentado para permitir búsquedas largas
            
            feed_locator = None 
            
            # Bucle Principal de Recolección
            while posts_scraped < target_count and scroll_attempts < max_scrolls_total:
                
                # 1. Identificar posts actuales
                feed = page.locator('div[role="feed"]')
                if feed.count() == 0: feed = page.locator('div[role="main"]')
                
                posts = None
                if feed.count() > 0:
                    posts = feed.locator('div[role="article"]')
                    if posts.count() == 0: posts = feed.locator('div[aria-posinset]')
                else:
                    posts = page.locator('div[role="article"]')
                
                current_post_count = posts.count()
                print(f"[Facebook] Posts visibles: {current_post_count} | Posts Procesados: {posts_scraped}/{target_count}")
                
                # 2. Procesar posts nuevos
                found_new_in_pass = False
                
                for i in range(current_post_count):
                    if posts_scraped >= target_count: 
                        break
                        
                    if i in processed_posts_indices:
                        continue # Ya procesado
                        
                    # Procesar Post
                    try:
                        post_body = posts.nth(i)
                        
                        # Scroll y Ancla
                        post_body.scroll_into_view_if_needed()
                        # time.sleep(1) 
                        
                        # --- 0. EXTRAER INFO DEL POST (Autor y Texto) ---
                        try:
                            # Autor: Estrategia Mejorada
                            post_author = "Desconocido"
                            
                            # 1. Buscar etiqueta Strong (muy común para nombres)
                            author_candidates = post_body.locator('strong, h2, h3').all()
                            for candlestick in author_candidates:
                                t = candlestick.inner_text().strip()
                                if len(t) > 2 and "Me gusta" not in t: # Filtro básico
                                    post_author = t
                                    break
                            
                            # 2. Si falló, buscar primer link que NO parezca fecha
                            if post_author == "Desconocido":
                                links = post_body.locator('div[data-ad-preview="message"] < div < div a').all() # Subir desde el mensaje
                                if not links:
                                     links = post_body.locator('span > a[role="link"]').all()
                                
                                for l in links:
                                    txt = l.inner_text().strip()
                                    if len(txt) > 3 and not re.search(r'\d+\s?[hm]', txt):
                                        post_author = txt
                                        break
                            
                            # LIMPIEZA DE AUTOR
                            if post_author:
                                # Eliminar "Seguir", "·", saltos de línea
                                post_author = post_author.replace("\n", " ").replace("Seguir", "").replace("·", "").strip()
                                # Si quedaron espacios dobles
                                post_author = re.sub(r'\s+', ' ', post_author).strip()

                            # Texto: Estrategia Mejorada
                            post_content = "Sin texto / Solo media"
                            # Buscamos bloques de texto significativos
                            text_divs = post_body.locator('div[dir="auto"]').all()
                            
                            content_parts = []
                            seen_texts = set()
                            
                            for div in text_divs:
                                txt = div.inner_text().strip()
                                
                                # Filtros anti-ruido
                                if (len(txt) > 3 
                                    and txt != post_author 
                                    and txt not in ["Me gusta", "Responder", "Compartir", "Ver más"]
                                    and not txt.startswith("Hace") # Fechas relativas
                                    ):
                                    
                                    # Evitar duplicados exactos o substrings muy obvios
                                    is_duplicate = False
                                    for existing in content_parts:
                                        if txt in existing or existing in txt:
                                            # Si uno contiene al otro, nos quedamos con el más largo
                                            if len(txt) > len(existing):
                                                content_parts.remove(existing)
                                                content_parts.append(txt)
                                            is_duplicate = True
                                            break
                                    
                                    if not is_duplicate and txt not in seen_texts:
                                        content_parts.append(txt)
                                        seen_texts.add(txt)
                            
                            if content_parts:
                                # Tomamos el más largo o unimos
                                post_content = " | ".join(content_parts)
                            
                            # Limpieza Definitiva del Post Content
                            post_content = post_content.replace("\n", " | ").replace("\r", "")
                            post_content = re.sub(r'\s+', ' ', post_content).strip()

                            print(f"[Post] Autor: '{post_author}' | Texto: {post_content[:40]}...")
                            
                            # NOTA: Ya no guardamos el post como fila independiente aquí.
                            # Lo guardaremos junto con cada comentario para mantener la relación.

                        except Exception as e_post:
                             print(f"Error extrayendo info del post: {e_post}")
                             post_author = "Error"
                             post_content = "Error"

                        # --- Lógica de apertura de comentarios (Reutilizada y compactada) ---
                        clicked = False
                        
                        # Intentar subir a contenedor padre si el locator es interno
                        first_post = post_body
                        
                        # Buscar botón comentarios (Abrir modal)
                        try:
                            # Prioridad: Botón "N comentarios"
                            comm_btn = first_post.locator('div[role="button"], span[role="button"]').filter(has_text=re.compile(r"\d+\s+comentarios?", re.IGNORECASE)).first
                            if comm_btn.count() > 0 and comm_btn.is_visible():
                                comm_btn.click(force=True)
                                clicked = True
                            else:
                                # Fallback: Botón "Comentar"
                                c_btn = first_post.locator('div[role="button"], span[role="button"]').filter(has_text="Comentar").first
                                if c_btn.count() > 0 and c_btn.is_visible():
                                    c_btn.click(force=True)
                                    clicked = True
                        except: pass
                        
                        # Fallback click coords
                        if not clicked:
                             try:
                                 like_btn = first_post.locator('div[aria-label^="Me gusta"], div[aria-label^="Reaccionar"]').first
                                 if like_btn.count() > 0:
                                     box = like_btn.bounding_box()
                                     if box:
                                         page.mouse.click(box["x"] + box["width"]/2, box["y"] - 50)
                                         clicked = True
                             except: pass
                        
                        if not clicked:
                            # Si no pudimos interactuar, guardamos el post sin comentarios
                            results.append({
                                "post_index": posts_scraped + 1,
                                "post_author": post_author,
                                "post_content": post_content,
                                "comment_author": "",
                                "comment_content": ""
                            })
                            posts_scraped += 1
                            processed_posts_indices.add(i)
                            continue
                            
                        time.sleep(2) # Esperar carga modal/despliegue (Reducido)
                        
                        # --- Extracción y Expansión de Comentarios ---
                        container = page
                        if page.locator('div[role="dialog"]').count() > 0:
                            container = page.locator('div[role="dialog"]').last
                        
                        # EXPANDIR COMENTARIOS (Clicar "Ver más" repetidamente)
                        print("   > Expandiendo comentarios (Max 10 intentos)...")
                        for _ in range(10): 
                            try:
                                # Prioridad 1: Click en botones "Ver más"
                                more_btns = container.locator('span:has-text("Ver más comentarios"), span:has-text("Ver comentarios previos"), div[role="button"]:has-text("Ver más")').all()
                                clicked_more = False
                                for btn in more_btns:
                                    if btn.is_visible():
                                        try:
                                            btn.click(force=True)
                                            clicked_more = True
                                            time.sleep(1.5)
                                        except: pass
                                
                                if not clicked_more:
                                    # Prioridad 2: Scroll agresivo para Lazy Loading
                                    # Buscamos el último comentario visible y hacemos scroll hacia él
                                    current_comments = container.locator('div[aria-label^="Comentario de"]')
                                    if current_comments.count() > 0:
                                        try:
                                            current_comments.last.scroll_into_view_if_needed()
                                            page.mouse.wheel(0, 500) # Un empujoncito extra
                                            time.sleep(1.5)
                                        except: 
                                            page.mouse.wheel(0, 1000)
                                    else:
                                        page.mouse.wheel(0, 1000)
                                        time.sleep(1)
                                    
                                    # Si tras el scroll no aparece botón nuevo y ya no carga más...
                                    # (Podríamos poner condiciones de salida más listas, pero el loop de 10 termina rápido)
                            except:
                                break

                        # Selectores comentarios
                        comments_loc = container.locator('div[aria-label^="Comentario de"]')
                        if comments_loc.count() == 0:
                             comments_loc = container.locator('div[role="article"]') # Genérico
                        
                        c_qty = comments_loc.count()
                        print(f"   > Post {posts_scraped+1}: {c_qty} comentarios encontrados.")
                        
                        post_comments_added = 0
                        # Si no hay comentarios, guardar al menos el post
                        if c_qty == 0:
                             results.append({
                                "platform": "Facebook",
                                "post_index": posts_scraped + 1,
                                "post_author": post_author,
                                "post_content": post_content,
                                "comment_author": "",
                                "comment_content": ""
                            })
                        
                        for j in range(c_qty):
                            try:
                                el = comments_loc.nth(j)
                                raw_text = el.inner_text()
                                lines = [l.strip() for l in raw_text.split('\n') if len(l.strip()) > 0]
                                
                                # Extraer autor/contenido
                                c_author = "Anon"
                                c_content = ""
                                
                                # Intento por aria-label (Suele ser el más limpio "Comentario de ...")
                                lbl = el.get_attribute("aria-label")
                                if lbl: 
                                    c_author = lbl.replace("Comentario de", "").strip()
                                
                                # Si no hay aria-label, usaremos el texto
                                if not c_author or c_author == "Anon":
                                     if len(lines) > 0: 
                                         c_author = lines[0]
                                
                                # LIMPIEZA DE AUTOR (Quitar fechas relativas que a veces se pegan)
                                # Ej: "Juan Perez Hace 2 horas" -> "Juan Perez"
                                c_author = re.split(r'\s+hace\s+', c_author, flags=re.IGNORECASE)[0].strip()
                                
                                # Contenido: Todo lo que no sea el autor, ni metadata
                                clean_lines = []
                                for l in lines:
                                    # Filtros estrictos
                                    if (l != c_author 
                                        and not l.startswith(c_author) # A veces el texto repite el autor
                                        and l not in ["Responder", "Me gusta", "Ocultar", "Editar"]
                                        and not re.match(r'^\d+\s?[hmys]$', l) # "4 h", "1 sem"
                                        and not re.match(r'^Hace\s+', l) 
                                        ):
                                        clean_lines.append(l)
                                
                                c_content = " ".join(clean_lines)
                                
                                # Limpieza final de contenido (a veces el autor sigue pegado al principio)
                                if c_content.startswith(c_author):
                                    c_content = c_content[len(c_author):].strip()

                                # QUITAR NUMEROS SUELTOS AL FINAL (Contadores de Likes)
                                # Ej: "texto del comentario 15" -> "texto del comentario"
                                c_content = re.sub(r'\s+\d+$', '', c_content).strip()

                                if len(c_content) > 0:
                                    results.append({
                                        "platform": "Facebook",
                                        "post_index": posts_scraped + 1,
                                        "post_author": post_author,
                                        "post_content": post_content, # Ya está limpio
                                        "comment_author": c_author,
                                        "comment_content": c_content
                                    })
                                    post_comments_added += 1
                            except: pass
                        
                        # Cerrar modal/post
                        page.keyboard.press("Escape")
                        time.sleep(0.5)
                        page.keyboard.press("Escape") # Doble por seguridad
                        
                    except Exception as e:
                        print(f"Err post {i}: {e}")
                        pass
                    
                    posts_scraped += 1
                    processed_posts_indices.add(i)
                    
                # 3. Decidir si hacer scroll
                if posts_scraped < target_count:
                    # Si no procesamos nada nuevo o ya acabamos los visibles
                    print("[Facebook] Scrolleando para más posts...")
                    page.mouse.wheel(0, 3000)
                    time.sleep(2) # Reducido
                    scroll_attempts += 1
                    
                    # Chequeo anti-bucle si no carga nada nuevo
                    new_post_count = posts.count() # (Este count podría ser stale, pero page.mouse.wheel refresca DOM)
                    # En Playwright 'posts' es localizador dinámico, posts.count() se reevalúa.
            
            print(f"[Facebook] Finalizado. Total comentarios: {len(results)}")
            
        except Exception as e:
            print(f"[Facebook] Error: {e}")
        finally:
            try:
                browser.close()
            except:
                pass
            
    return results
