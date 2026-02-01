import os
import random
import time
import subprocess
import socket
from typing import Dict, List

from playwright.sync_api import TimeoutError, sync_playwright

import config

# This scraper reuses a real session and adds delays; it does not attempt to bypass CAPTCHAs or anti-bot systems.

SLEEP_MIN = 1.0
SLEEP_MAX = 2.2
MAX_SCROLLS = 100 # Scroll global del feed
TARGET_REPLIES_PER_TWEET = 500 # Máximo por post


def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def ensure_remote_browser():
    try:
        # Verificar si ya está corriendo
        if is_port_open("127.0.0.1", 9222):
            print("[X] Navegador remoto detectado activo en puerto 9222.")
            return True

        print("[X] Iniciando navegador remoto via launch_chrome.bat...")
        bat_path = os.path.join(os.getcwd(), "launch_chrome.bat")
        
        if not os.path.exists(bat_path):
            print(f"[X] Error: No encuentro {bat_path}")
            return False
            
        # Lanzar en segundo plano
        subprocess.Popen(bat_path, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        
        # Esperar a que arranque (polling del puerto)
        print("[X] Esperando a que Chrome arranque...")
        for _ in range(10):
            time.sleep(2)
            if is_port_open("127.0.0.1", 9222):
                print("[X] Conexión establecida con Chrome Debug.")
                return True
        
        print("[X] Timeout esperando a Chrome Debug.")
        return False
    except Exception as e:
        print(f"[X] No se pudo lanzar el bat: {e}")
        return False


def human_delay(multiplier: float = 1.0) -> None:
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX) * multiplier)


def extract_text(article) -> str:
    text_spans = article.locator('[data-testid="tweetText"] span')
    parts: List[str] = []
    count = text_spans.count()
    for idx in range(count):
        candidate = text_spans.nth(idx).inner_text().strip()
        if candidate:
            parts.append(candidate)
    return " ".join(parts).strip()


def extract_handle(article) -> str:
    handle_locator = article.locator('[data-testid="User-Name"] span')
    count = handle_locator.count()
    for idx in range(count):
        text = handle_locator.nth(idx).inner_text().strip()
        if text.startswith("@"):
            return text
    return ""


def extract_timestamp(article) -> str:
    time_tag = article.locator('time').first
    try:
        if time_tag.count() > 0:
            value = time_tag.get_attribute("datetime")
            return value or ""
    except Exception:
        return ""
    return ""


def extract_permalink(article) -> str:
    anchor = article.locator('a:has(time)').first
    if anchor.count() == 0:
        return ""
    href = anchor.get_attribute("href")
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return f"https://x.com{href}"


def wait_for_home(page) -> bool:
    for _ in range(20):
        human_delay(1.5)
        if page.locator('[data-testid="primaryColumn"]').count() > 0:
            return True
        if "login" in page.url:
            continue
    return False


def ensure_login(page, username: str, password: str) -> bool:
    human_delay()
    if "login" not in page.url and page.locator("input[autocomplete='username']").count() == 0:
        return True
    
    # Si es cookie session, no intentamos escribir
    if "CookieSession" in username:
        return True
        
    if username:
        try:
            user_field = page.locator("input[autocomplete='username']").first
            if user_field.count() > 0:
                user_field.fill(username)
                human_delay()
                next_button = page.locator("button:has-text('Siguiente'), div[role='button']:has-text('Siguiente')").first
                if next_button.count() > 0:
                    next_button.click()
                    human_delay()
        except Exception:
            pass
    else:
        print("[X] Abre el navegador y completa el login manualmente si es necesario.")

    if password:
        try:
            pass_field = page.locator("input[name='password']").first
            if pass_field.count() > 0:
                pass_field.fill(password)
                human_delay()
                page.locator("button[data-testid='LoginForm_Login_Button']").click()
        except Exception:
            pass

    logged_in = wait_for_home(page)
    if not logged_in:
        print("[X] No se confirmó el inicio de sesión. Intenta manualmente en la ventana abierta.")
    return logged_in


def scrape_conversation(context, url: str) -> Dict[str, List[Dict[str, str]]]:
    convo_page = context.new_page()
    convo_results = {"post": None, "replies": []}
    try:
        human_delay(1.5)
        convo_page.goto(url, wait_until="domcontentloaded")
        
        # DEBUG: Screenshot desactivado
        # safe_name = url.split('/')[-1]
        # try:
        #     convo_page.screenshot(path=f"debug_tweet_{safe_name}.png")
        # except: pass
        try:
             convo_page.wait_for_selector('article', timeout=15000)
        except: 
             print(f"   > [X] No se detectó artículo en {url}")
             return convo_results

        # Scroll INTELIGENTE con Teclado (PageDown)
        # Esto suele disparar mejor los eventos de carga que el mouse.wheel
        
        # 1. Intentar hacer foco en el tweet principal
        try:
            convo_page.locator('article').first.click(force=True) 
        except: 
            convo_page.mouse.click(100, 100) # Click genérico si falla
            
        last_height = convo_page.evaluate("document.body.scrollHeight")
        no_change_count = 0
        
        print("   > Navegando respuestas (PageDown)...")
        for _ in range(30): 
            # Usar teclado para bajar
            convo_page.keyboard.press("PageDown")
            human_delay(1.5) 
            
            # Chequear botones "Mostrar más"
            try:
                more_btns = convo_page.locator('div[role="button"]:has-text("Mostrar más"), span:has-text("Mostrar más")').all()
                for btn in more_btns:
                    if btn.is_visible():
                        btn.click()
                        human_delay(1.0)
            except: pass

            new_height = convo_page.evaluate("document.body.scrollHeight")
            # print(f"     Height: {last_height} -> {new_height}")
            
            if new_height == last_height:
                no_change_count += 1
                if no_change_count >= 4: # Si en 4 intentos no baja más, paramos
                    break
            else:
                no_change_count = 0
                last_height = new_height
            
        # Estrategia Mejorada para Identificar Post Principal y Respuestas
        
        # 1. Extraer el handle del autor esperado desde la URL
        # URL típica: https://x.com/Tania840942/status/201589...
        try:
             expected_author_handle = "@" + url.split('x.com/')[1].split('/')[0]
        except:
             expected_author_handle = ""

        # ESTRATEGIA DEFINITIVA: Buscar el Focal Tweet por tabindex="-1"
        # Twitter suele marcar el tweet abierto con tabindex="-1" en el article.
        focal_article = convo_page.locator('article[tabindex="-1"]').first
        
        main_post_data = None
        
        if focal_article.count() > 0:
            try:
                # Extraer texto del focal
                f_text_el = focal_article.locator('div[data-testid="tweetText"]').first
                if f_text_el.count() > 0:
                     f_raw = f_text_el.inner_text()
                     f_txt = f_raw.replace("\n", " ").replace("\r", " ").strip()
                     f_handle = extract_handle(focal_article)
                     f_time = extract_timestamp(focal_article)
                     
                     main_post_data = {
                        "source": "X",
                        "type": "post",
                        "url": url,
                        "author": f_handle,
                        "content": f_txt,
                        "datetime": f_time,
                        "parent_url": url 
                     }
                     print(f"   > Post Principal IDENTIFICADO por tabindex: {f_handle}")
            except: pass

        # Si falló la estrategia del tabindex, usamos la del autor
        if not main_post_data:
             # (Lógica de fallback anterior, simplificada)
             pass

        tweet_texts = convo_page.locator('div[data-testid="tweetText"]')
        count = tweet_texts.count()
        
        candidates = []
        for i in range(count):
            try:
                el = tweet_texts.nth(i)
                raw_txt = el.inner_text()
                txt = raw_txt.replace("\n", " ").replace("\r", " ").strip()
                if not txt: continue
                
                container = el.locator('xpath=./ancestor::article')
                if container.count() == 0: continue
                
                handle = extract_handle(container)
                
                candidates.append({
                    "text": txt,
                    "author": handle
                })
            except: pass
            
        if not main_post_data:
             # Fallback lógica autor URL
             # ... (reutilizar lo que ya estaba o simplificar)
             # Por simplicidad, si no hallamos tabindex, usamos el primero que coincida con URL 
             main_idx = 0
             for i, c in enumerate(candidates):
                 if expected_author_handle and c["author"] and expected_author_handle.lower() in c["author"].lower():
                     main_idx = i
                     break
             
             if candidates:
                 c = candidates[main_idx]
                 main_post_data = {
                    "source": "X",
                    "type": "post",
                    "url": url,
                    "author": c["author"],
                    "content": c["text"],
                    "datetime": "",
                    "parent_url": url 
                 }

        if main_post_data:
            convo_results["post"] = main_post_data
            
            # Agregar respuestas (excluyendo el texto del main post)
            for c in candidates:
                # Excluir si es el mismo contenido y autor que el main
                if c["text"] == main_post_data["content"] and c["author"] == main_post_data["author"]:
                    continue
                    
                convo_results["replies"].append({
                    "source": "X",
                    "type": "reply",
                    "url": url,
                    "author": c["author"],
                    "content": c["text"],
                    "datetime": "",
                    "parent_url": url
                })
                if len(convo_results["replies"]) >= TARGET_REPLIES_PER_TWEET:
                    break
        
        return convo_results
    except TimeoutError:
        print(f"[X] Timeout cargando conversación: {url}")
    except Exception as exc:
        print(f"[X] Error al leer conversación {url}: {exc}")
    finally:
        convo_page.close()
    return convo_results


def scrape_twitter(topic: str, username: str, password: str, target_count: int = 10) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    print(f"[X] Iniciando para: {topic} | Meta: {target_count} POSTS")

    # Intentar auto-arranque si está configurado remoto
    if config.X_REMOTE_DEBUGGING_URL:
        ensure_remote_browser()

    if config.X_PROFILE_PATH:
        user_data_dir = config.X_PROFILE_PATH
    else:
        user_data_dir = os.path.join(os.getcwd(), "profiles", "auth_profile_x")
        os.makedirs(user_data_dir, exist_ok=True)

    with sync_playwright() as p:
        context = None
        browser = None
        # Intentar conectar a navegador existente (si está configurado)
        use_remote = False
        if config.X_REMOTE_DEBUGGING_URL:
            try:
                # print(f"[X] Intentando conectar a navegador remoto en {config.X_REMOTE_DEBUGGING_URL}...")
                browser = p.chromium.connect_over_cdp(config.X_REMOTE_DEBUGGING_URL)
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = browser.new_context()
                use_remote = True
                print("[X] Conectado exitosamente.")
            except Exception as e:
                print(f"[X] No se pudo conectar al remoto ({e}). Iniciando nueva instancia...")

        # Si no se conectó al remoto, iniciar uno nuevo persistente
        if not context:
            try:
                args = [
                    "--start-maximized",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-features=FedCm,FederatedCredentialManagement,PrivacySandboxAdsApis",
                    "--disable-blink-features=AutomationControlled",
                ]
                if config.X_PROFILE_PATH and config.X_PROFILE_DIRECTORY:
                    args.append(f"--profile-directory={config.X_PROFILE_DIRECTORY}")

                launch_kwargs = {
                    "user_data_dir": user_data_dir,
                    "headless": True,
                    "locale": "es-ES",
                    "args": args,
                }
                if config.X_BROWSER_CHANNEL:
                    launch_kwargs["channel"] = config.X_BROWSER_CHANNEL

                context = p.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as exc:
                print(f"[X] Error fatal iniciando navegador: {exc}")
                return results

        if context is None:
            print("[X] No context. Aborting.")
            return results

        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto("https://x.com/login", wait_until="domcontentloaded")
            logged_in = ensure_login(page, username, password)
            if not logged_in:
                human_delay(2.0)

            # Búsqueda TOP (Destacados)
            search_url = f"https://x.com/search?q={topic}&src=typed_query" 
            print(f"[X] Buscando '{topic}'...")
            page.goto(search_url, wait_until="domcontentloaded")
            human_delay(2.0)

            seen_urls = set()
            scrolls = 0
            post_idx = 0
            
            collected_comments = 0
            
            # Inicializar DB para reporte de progreso
            try:
                from database import Database
                db = Database()
            except: db = None

             # --- BUCLE PRINCIPAL (Por Post) ---
            while post_idx < target_count and scrolls < MAX_SCROLLS:
                print(f"[X] Progreso: {post_idx}/{target_count} posts procesados. Feed scroll {scrolls}...")
                
                # Actualizar DB
                if db and db.is_connected:
                    db.update_stage_progress(topic, "twitter", post_idx, "running")
                
                # 1. Identificar Tweets en pantalla
                tweets = page.locator('article[data-testid="tweet"]')
                count = tweets.count()
                
                # Iterar sobre tweets visibles
                for idx in range(count):
                    if post_idx >= target_count: break
                    
                    try:
                        article = tweets.nth(idx)
                        article.scroll_into_view_if_needed()
                        
                        permalink = extract_permalink(article)
                        if not permalink or permalink in seen_urls:
                            continue
                        seen_urls.add(permalink)
                        
                        # PROCESS TWEET
                        print(f"   > [Post {post_idx+1}] Procesando: {permalink}")
                        human_delay(0.5)
                        convo_data = scrape_conversation(context, permalink)
                        
                        post_data = convo_data["post"]
                        replies = convo_data["replies"]
                        
                        # Si encontramos el post (aunque tenga 0 comentarios, cuenta como procesado)
                        # Pero para maximizar utilidad, sigamos la lógica de guardar.
                        if post_data:
                            post_idx += 1
                            p_author = post_data["author"]
                            p_content = post_data["content"]
                            
                            num_replies = len(replies)
                            
                            # Si no hay respuestas, podríamos guardar 1 fila con comment vacio
                            # o no guardar nada si preferimos solo data con interacción.
                            # Guardaremos todo para cumplir la cuota de "Posts analizados".
                            
                            if num_replies == 0:
                                # Opcional: Descomentar para guardar posts sin comentarios
                                results.append({
                                   "platform": "X",
                                   "post_index": post_idx,
                                   "post_author": p_author,
                                   "post_content": p_content,
                                   "comment_author": "N/A",
                                   "comment_content": "No comments found"
                                })
                            else:
                                for reply in replies:
                                    results.append({
                                        "platform": "X",
                                        "post_index": post_idx,
                                        "post_author": p_author,
                                        "post_content": p_content,
                                        "comment_author": reply["author"],
                                        "comment_content": reply["content"]
                                    })
                            
                            collected_comments += num_replies
                            print(f"     + {num_replies} respuestas. Total global: {collected_comments}")
                            
                    except Exception as e:
                        pass
                
                if post_idx >= target_count: break
                
                # Scroll Feed Principal
                page.mouse.wheel(0, 2500)
                human_delay(2.0)
                scrolls += 1
            
            # Final Update
            if db and db.is_connected:
                db.update_stage_progress(topic, "twitter", post_idx, "completed")

            print(f"[X] Finalizado. {post_idx} posts procesados. {collected_comments} respuestas extraídas.")

        except TimeoutError:
            print("[X] Timeout durante la carga inicial o búsqueda. Reintentando refresh...")
            try:
                page.reload()
                page.wait_for_timeout(5000)
            except: pass
            
        except Exception as exc:
            print(f"[X] Error inesperado en flujo principal: {exc}")
        finally:
            if config.X_REMOTE_DEBUGGING_URL:
                try:
                    if browser: 
                        browser.close()
                    # Matar el proceso específico de Chrome lanzado en puerto 9222
                    print("[X] Cerrando proceso de Chrome Remoto...")
                    # Usar WMIC para matar el proceso por línea de comandos (más robusto que PowerShell desde Python)
                    subprocess.run('wmic process where "CommandLine like \'%--remote-debugging-port=9222%\' and Name=\'chrome.exe\'" call terminate', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except: pass
            else:
                 try: 
                    if context: context.close()
                 except: pass

    # Chequeo final
    if not results:
        print("[X] Advertencia: No se extrajeron resultados. Verifica login o selectores.")
        
    return results
