from playwright.sync_api import sync_playwright
import os
import re
import time
import random
from urllib.parse import quote_plus

def human_delay(min_s=1.2, max_s=2.8):
    time.sleep(random.uniform(min_s, max_s))

def scrape_instagram(topic: str, username: str, password: str, target_count: int = 5):
    """
    Scraper robusto de Instagram por Hashtag.
    - topic: Hashtag (sin #)
    - target_count: Cantidad de POSTS a analizar (no comentarios totales)
    """
    user_data_dir = os.path.join(os.getcwd(), "profiles", "auth_profile_instagram")
    os.makedirs(user_data_dir, exist_ok=True)

    hashtag = topic.strip().lstrip("#").replace(" ", "").lower()
    start_url = f"https://www.instagram.com/explore/tags/{quote_plus(hashtag)}/"
    
    results = []
    
    print(f"[Instagram] Iniciando scraper para #{hashtag} | Meta: {target_count} posts")

    with sync_playwright() as p:
        # Configuración "Ninja"
        args = [
            "--start-maximized",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ]

        ctx = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=True, # Ver proceso
            args=args,
            viewport=None,
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(60000)

        try:
            # 1. Navegar al Hashtag
            print(f"[Instagram] Navegando a: {start_url}")
            page.goto(start_url, wait_until="domcontentloaded")
            time.sleep(3)

            # Check Login
            if "/accounts/login" in page.url:
                print("[Instagram] Redirigido a Login. Intentando esperar login manual si el usuario está mirando...")
                time.sleep(5)
                if "/accounts/login" in page.url:
                    print("[Error] No hay sesión iniciada. Ejecuta 'python login_manual.py --site instagram' primero.")
                    ctx.close()
                    return []

            # 2. Recolectar URLs de Posts
            post_urls = set()
            scrolls = 0
            print("[Instagram] Recolectando URLs de posts...")
            
            # Scrollear hasta tener suficientes
            while len(post_urls) < target_count and scrolls < 10:
                # Extraer hrefs que cumplan patrón /p/ o /reel/
                hrefs = page.locator('a[href^="/p/"], a[href^="/reel/"]').all()
                for link in hrefs:
                    url = link.get_attribute("href")
                    if url:
                        full_url = "https://www.instagram.com" + url
                        post_urls.add(full_url)
                
                if len(post_urls) >= target_count:
                    break
                
                page.mouse.wheel(0, 4000)
                time.sleep(2)
                scrolls += 1
            
            target_urls = list(post_urls)[:target_count]
            print(f"[Instagram] Se procesarán {len(target_urls)} posts.")

            # 3. Procesar cada Post
            for i, p_url in enumerate(target_urls):
                print(f"\n[Instagram] ({i+1}/{len(target_urls)}) Procesando: {p_url}")
                try:
                    page.goto(p_url, wait_until="domcontentloaded")
                    time.sleep(3)
                    
                    # --- EXTRAER INFO DEL POST (USANDO METADATOS) ---
                    post_author = "Desconocido"
                    post_content = "Sin descripción"
                    
                    try:
                        # Método MetaTags (Muy robusto según tu ejemplo)
                        # Content format: "15K likes, 67 comments - AUTOR el DATE: "DESCRIPCION""
                        og_desc = page.locator('meta[property="og:description"]').get_attribute("content")
                        if og_desc:
                            # 1. Extraer Autor (entre "- " y " el ")
                            if " - " in og_desc and " el " in og_desc:
                                parts = og_desc.split(" - ")[1].split(" el ")
                                post_author = parts[0].strip()
                            
                            # 2. Extraer Contenido (lo que está entre comillas después de los dos puntos)
                            # A veces no hay comillas si es corto, o formato varía.
                            if ': "' in og_desc:
                                post_content = og_desc.split(': "', 1)[1].rstrip('".')
                            elif ": " in og_desc:
                                post_content = og_desc.split(": ", 1)[1]
                            
                            print(f"   > [Meta] Autor: {post_author}")
                    except Exception as e_meta:
                        print(f"   > Error meta: {e_meta}")

                    # Fallback visual para Autor si falló meta
                    if post_author == "Desconocido":
                        try:
                            # Header h2 o primer link
                            header_text = page.locator("header h2").first.inner_text()
                            if header_text: post_author = header_text
                        except: pass

                    print(f"   > Post Autor: {post_author} | Desc: {post_content[:30]}...")

                    # --- CARGAR COMENTARIOS ---
                    print("   > Expandiendo comentarios (Max 50 clicks/scroll)...")
                    consecutive_not_found = 0
                    
                    # Pre-chequeo del límite para no expandir de más
                    # (Leemos la variable que se define más abajo, o usamos un valor default alto si no existe aun)
                    current_limit = 50 

                    for _ in range(50):
                        try:
                            # Chequeo rápido de cantidad actual
                            current_candidates = page.locator('div[role="button"]:has-text("Responder"), div[role="button"]:has-text("Reply"), span:has-text("Responder")').count()
                            if current_candidates >= current_limit + 10: 
                                print("   > Límite de comentarios alcanzado visualmente. Deteniendo carga.")
                                break

                            found_button = False
                            # 1. Botón circular (+) típico
                            btn_svg = page.locator('svg[aria-label="Cargar más comentarios"]').locator("..")
                            if btn_svg.count() > 0 and btn_svg.first.is_visible():
                                btn_svg.first.click()
                                found_button = True
                            
                            # 2. Botón de texto "Ver más comentarios" (alternativo)
                            if not found_button:
                                btn_txt = page.locator('button:has-text("Ver más comentarios")')
                                if btn_txt.count() > 0 and btn_txt.first.is_visible():
                                    btn_txt.first.click()
                                    found_button = True

                            if found_button:
                                consecutive_not_found = 0
                                time.sleep(1.5) # Esperar carga (reducido de 2)
                            else:
                                # Scroll y conteo de fallos
                                page.mouse.wheel(0, 600)
                                time.sleep(0.8)
                                consecutive_not_found += 1
                                
                                if consecutive_not_found >= 3:
                                    # Si fallamos 3 veces seguidas (scroll y no botón), asumimos fln
                                    break
                        except: break

                    # --- EXPANDIR RESPUESTAS ANIDADAS (NUEVO) ---
                    # Basado en tu HTML: "Ver las 1 respuestas"
                    print("   > Expandiendo sub-respuestas (puede tardar)...")
                    try:
                        # Buscar botones que digan "Ver las..." o "View replies"
                        # Usamos un selector generico de texto
                        nested_btns = page.locator('div[role="button"] span:has-text("Ver las"), div[role="button"] span:has-text("View replies")').all()
                        
                        # Limitamos a clicar unos 10-20 para no eternizar
                        clicks = 0
                        for btn in nested_btns:
                            if clicks > 50: break
                            if btn.is_visible():
                                try:
                                    btn.click(force=True)
                                    time.sleep(0.5)
                                    clicks += 1
                                except: pass
                        if clicks > 0:
                            print(f"   > Se expandieron {clicks} hilos de respuestas.")
                            time.sleep(2) # Esperar que rendericen
                    except: pass

                    # --- EXTRAER COMENTARIOS (NUEVA ESTRATEGIA: POR BOTÓN "RESPONDER") ---
                    comments_found = 0
                    seen_comments = set()
                    
                    try:
                        # Cada comentario tiene un botón "Responder" (o "Reply")
                        # Buscamos todos esos botones
                        reply_btns = page.locator('div[role="button"]:has-text("Responder"), div[role="button"]:has-text("Reply")').all()
                        
                        # Si no encuentra por role=button, busca por texto span
                        if not reply_btns:
                             reply_btns = page.locator('span:has-text("Responder"), span:has-text("Reply")').all()
                        
                        print(f"   > Candidatos (botones responder): {len(reply_btns)}")
                        
                        limit_comments_per_post = 100
                        
                        for btn in reply_btns:
                            if comments_found >= limit_comments_per_post: break
                            
                            try:
                                # El texto del comentario suele estar:
                                # 1. En un contenedor padre del botón 'Responder'.
                                # 2. Específicamente, en un <span> o <div> hermano o tío.
                                
                                # Subimos al contenedor del comentario (LI o DIV wrapper)
                                # Normalmente el botón responder está en una fila de acciones. El texto está arriba.
                                
                                # Intentamos subir 3-4 niveles hasta abarcar todo el bloque del comentario
                                comment_block = btn.locator('xpath=./../../../../..') 
                                
                                # Extraemos todo el texto del bloque
                                block_text = comment_block.inner_text()
                                lines = [l.strip() for l in block_text.split('\n') if l.strip()]
                                
                                if not lines: continue
                                
                                # Parseo Heurístico
                                # Normalmente: 
                                # [FOTO]
                                # AUTOR (con verificado opcional)
                                # TEXTO
                                # FECHA - RESPONDER - TRADUCIR
                                
                                c_author = lines[0] # Primera línea suele ser autor
                                c_content = ""
                                
                                # Filtrar líneas basura
                                clean_lines = []
                                for l in lines[1:]:
                                    if (l != c_author 
                                        and "Responder" not in l 
                                        and "Reply" not in l
                                        and "Me gusta" not in l
                                        and not re.match(r'^\d+[smhdw]$', l) # Fechas cortas
                                        and "Ver traducción" not in l
                                        ):
                                        clean_lines.append(l)
                                
                                c_content = " ".join(clean_lines)

                                # Limpieza EXTRA: Quitar fechas del principio del contenido (Ej: "3 sem Hola")
                                c_content = re.sub(r'^\d+\s+(sem|sem\.|d|h|m|s|w)\s+', '', c_content).strip()
                                
                                # Validar
                                if len(c_content) > 1 and c_content not in seen_comments:
                                    # Evitar que sea la descripción del post repetida
                                    if c_author == post_author and (post_content in c_content or c_content in post_content):
                                        continue
                                    
                                    # Limpieza final de Post Content (por seguridad)
                                    clean_post = post_content.replace("\n", " | ").replace("\r", "").strip()

                                    results.append({
                                        "platform": "Instagram",
                                        "post_index": i + 1,
                                        "post_author": post_author,
                                        "post_content": clean_post,
                                        "comment_author": c_author,
                                        "comment_content": c_content
                                    })
                                    seen_comments.add(c_content)
                                    comments_found += 1
                                    
                            except: pass
                            
                    except Exception as e_comm:
                        print(f"   > Error extrayendo comentarios: {e_comm}")

                    print(f"   > Comentarios extraídos: {comments_found}")

                except Exception as e:
                    print(f"[Error] Fallo procesando {p_url}: {e}")

        except Exception as e:
            print(f"[Error Global] {e}")
            pass
        finally:
            ctx.close()

    return results
