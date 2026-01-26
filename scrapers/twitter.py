import os
import random
import time
from typing import Dict, List

from playwright.sync_api import TimeoutError, sync_playwright

import config

# This scraper reuses a real session and adds delays; it does not attempt to bypass CAPTCHAs or anti-bot systems.

SLEEP_MIN = 1.0
SLEEP_MAX = 2.2
MAX_SCROLLS = 6
TARGET_TWEETS = 12
TARGET_REPLIES_PER_TWEET = 15


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
        human_delay(1.2)
        convo_page.goto(url, wait_until="domcontentloaded")
        convo_page.wait_for_selector('article', timeout=20000)
        human_delay()
        articles = convo_page.locator('article')
        total = articles.count()
        for idx in range(total):
            article = articles.nth(idx)
            text = extract_text(article)
            if not text:
                continue
            handle = extract_handle(article)
            timestamp = extract_timestamp(article)
            permalink = extract_permalink(article)
            entry = {
                "source": "X",
                "type": "post" if idx == 0 else "reply",
                "url": permalink or url,
                "author": handle,
                "content": text,
                "datetime": timestamp,
                "parent_url": url if idx > 0 else url,
            }
            if idx == 0 and convo_results["post"] is None:
                convo_results["post"] = entry
            else:
                convo_results["replies"].append(entry)
            if len(convo_results["replies"]) >= TARGET_REPLIES_PER_TWEET:
                break
    except TimeoutError:
        print(f"[X] Timeout cargando conversación: {url}")
    except Exception as exc:
        print(f"[X] Error al leer conversación {url}: {exc}")
    finally:
        convo_page.close()
    return convo_results


def scrape_twitter(topic: str, username: str, password: str, target_count: int = 10) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    print(f"[X] Iniciando hilo para: {topic} | Meta: {target_count}")

    if config.X_PROFILE_PATH:
        user_data_dir = config.X_PROFILE_PATH
    else:
        user_data_dir = os.path.join(os.getcwd(), "auth_profile_x")
        os.makedirs(user_data_dir, exist_ok=True)

    with sync_playwright() as p:
        context = None
        browser = None
        try:
            if config.X_REMOTE_DEBUGGING_URL:
                browser = p.chromium.connect_over_cdp(config.X_REMOTE_DEBUGGING_URL)
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = browser.new_context()
            else:
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
                    "headless": False,
                    "locale": "es-ES",
                    "args": args,
                }
                if config.X_BROWSER_CHANNEL:
                    launch_kwargs["channel"] = config.X_BROWSER_CHANNEL

                context = p.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as exc:
            print(f"[X] No se pudo iniciar el navegador persistente: {exc}")
            return results

        if context is None:
            print("[X] No se pudo obtener un contexto de navegador para scraping.")
            return results

        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto("https://x.com/login", wait_until="domcontentloaded")
            logged_in = ensure_login(page, username, password)
            if not logged_in:
                human_delay(2.0)

            search_url = f"https://x.com/search?q={topic}&src=typed_query&f=live"
            print(f"[X] Buscando '{topic}'...")
            page.goto(search_url, wait_until="domcontentloaded")
            human_delay(2.0)

            seen_urls = set()
            scrolls = 0
            
            # --- MODIFICADO: Contar Comentarios (Respuestas), no solo Posts ---
            collected_comments = 0
            
            # Bucle infinito hasta cumplir meta de comentarios
            while collected_comments < target_count and scrolls < 50:
                print(f"[X] Bucle principal: {collected_comments}/{target_count} comentarios. Scroll {scrolls}...")
                
                # 1. Identificar Tweets en pantalla
                tweets = page.locator('article[data-testid="tweet"]')
                count = tweets.count()
                
                # Iterar sobre tweets visibles
                for idx in range(count):
                    if collected_comments >= target_count: break
                    
                    try:
                        article = tweets.nth(idx)
                        article.scroll_into_view_if_needed()
                        
                        permalink = extract_permalink(article)
                        if not permalink or permalink in seen_urls:
                            continue
                        seen_urls.add(permalink)
                        
                        # Scrape Conversación (Aquí es donde sacamos los comentarios/respuestas)
                        human_delay(0.5)
                        convo_data = scrape_conversation(context, permalink)
                        
                        # Guardar Post Original (Opcional, pero útil para contexto)
                        if convo_data["post"]:
                            results.append(convo_data["post"])
                        
                        # Guardar Respuestas (Estos son los "comentarios")
                        replies = convo_data["replies"]
                        if replies:
                            results.extend(replies)
                            collected_comments += len(replies)
                            print(f"   > +{len(replies)} respuestas extraídas. Total: {collected_comments}")
                            
                    except Exception as e:
                        # print(f"Err tweet {idx}: {e}")
                        pass
                
                if collected_comments >= target_count: break
                
                # Scroll para ver más tweets
                page.mouse.wheel(0, 2500)
                human_delay(2.0)
                scrolls += 1
            
            print(f"[X] Finalizado. {len(results)} items totales ({collected_comments} respuestas).")

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
                    if browser: browser.close()
                except: pass
            else:
                 try: 
                    if context: context.close()
                 except: pass

    # Chequeo final
    if not results:
        print("[X] Advertencia: No se extrajeron resultados. Verifica login o selectores.")
        
    return results
