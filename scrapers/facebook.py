from playwright.sync_api import sync_playwright
import time
import os
import random

import re

def scrape_facebook(topic, email, password, target_count=10):
    results = []
    print(f"[Facebook] Iniciando hilo para: {topic} | Meta: {target_count}")
    
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
            
            collected_comments_count = 0
            processed_posts_indices = set()
            
            scroll_attempts = 0
            max_scrolls_total = 50 # Aumentado para permitir búsquedas largas
            
            feed_locator = None 
            
            # Bucle Principal de Recolección
            while collected_comments_count < target_count and scroll_attempts < max_scrolls_total:
                
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
                print(f"[Facebook] Posts visibles: {current_post_count} | Comentarios recolectados: {collected_comments_count}/{target_count}")
                
                # 2. Procesar posts nuevos
                found_new_in_pass = False
                
                for i in range(current_post_count):
                    if collected_comments_count >= target_count: 
                        break
                        
                    if i in processed_posts_indices:
                        continue # Ya procesado
                        
                    # Procesar Post
                    try:
                        post_body = posts.nth(i)
                        
                        # Scroll y Ancla
                        post_body.scroll_into_view_if_needed()
                        # time.sleep(1) 
                        
                        # --- Lógica de apertura de comentarios (Reutilizada y compactada) ---
                        clicked = False
                        
                        # Intentar subir a contenedor padre si el locator es interno
                        first_post = post_body
                        
                        # Buscar botón comentarios
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
                            # Si no pudimos interactuar, saltamos
                            processed_posts_indices.add(i)
                            continue
                            
                        time.sleep(4) # Esperar carga modal/despliegue
                        
                        # --- Extracción ---
                        container = page
                        # Si hay modal
                        if page.locator('div[role="dialog"]').count() > 0:
                            container = page.locator('div[role="dialog"]').last
                            
                        # Selectores comentarios
                        comments_loc = container.locator('div[aria-label^="Comentario de"]')
                        if comments_loc.count() == 0:
                             comments_loc = container.locator('div[role="article"]') # Genérico
                        
                        c_qty = comments_loc.count()
                        print(f"   > Post {i}: {c_qty} candidatos.")
                        
                        post_comments_added = 0
                        for j in range(c_qty):
                            if collected_comments_count >= target_count: break
                            try:
                                el = comments_loc.nth(j)
                                raw_text = el.inner_text()
                                # Limpieza básica para extraer contenido real
                                # (Simplificado para velocidad, mejorable con parsing fino)
                                lines = [l.strip() for l in raw_text.split('\n') if len(l.strip()) > 2]
                                content = " ".join(lines)
                                
                                if len(content) > 3 and "Comentar" not in content:
                                    # Extraer autor si posible (primer línea suele ser autor)
                                    author = lines[0] if lines else "Anon"
                                    text_body = " ".join(lines[1:]) if len(lines) > 1 else content
                                    
                                    results.append({
                                        "source": "Facebook", "type": "comment",
                                        "author": author, "content": text_body
                                    })
                                    collected_comments_count += 1
                                    post_comments_added += 1
                            except: pass
                        
                        if post_comments_added > 0:
                            found_new_in_pass = True
                            
                        # Cerrar modal/post
                        page.keyboard.press("Escape")
                        time.sleep(0.5)
                        page.keyboard.press("Escape") # Doble por seguridad
                        
                    except Exception as e:
                        # print(f"Err post {i}: {e}")
                        pass
                    
                    processed_posts_indices.add(i)
                    
                # 3. Decidir si hacer scroll
                if collected_comments_count < target_count:
                    # Si no procesamos nada nuevo o ya acabamos los visibles
                    print("[Facebook] Scrolleando para más posts...")
                    page.mouse.wheel(0, 3000)
                    time.sleep(4)
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
