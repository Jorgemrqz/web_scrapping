import os
import time
import random
from playwright.sync_api import sync_playwright

def human_delay(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def scrape_linkedin(topic, email, password, target_count=10):
    results = []
    print(f"[LinkedIn] Iniciando hilo para: {topic} | Objetivo: {target_count}")
    
    user_data_dir = os.path.join(os.getcwd(), "auth_profile_linkedin")
    
    # User Agent de Windows
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
            
        page.set_default_timeout(60000)

        try:
            # 1. Navegación / Login
            print("[LinkedIn] Entrando al feed...")
            try:
                page.goto("https://www.linkedin.com/feed/", timeout=60000, wait_until="commit")
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[LinkedIn] Aviso cargando feed: {e}")

            human_delay(2, 4)
            
            # Verificación de login
            if "login" in page.url or "guest" in page.url or "people/urn" in page.url:
                print("[LinkedIn] ALERTA: Posible login requerido.")
                try:
                    if email and password and page.locator("#username").is_visible():
                        print("[LinkedIn] Rellenando credenciales...")
                        page.fill("#username", email)
                        human_delay(1, 2)
                        page.fill("#password", password)
                        human_delay(1, 2)
                        page.click("button[type='submit']")
                        page.wait_for_timeout(5000)
                except:
                    pass
            
            # 2. Búsqueda
            print(f"[LinkedIn] Buscando: '{topic}'...")
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={topic}&origin=GLOBAL_SEARCH_HEADER"
            
            try:
                page.goto(search_url, timeout=60000, wait_until="commit")
                print("[LinkedIn] Esperando carga de resultados...")
                # Espera fija para asegurar carga de JS
                time.sleep(5)
                
                # Espera fija para asegurar carga de JS
                time.sleep(5)
                
                # (Debug snapshot removido para producción)

                
            except Exception as e:
                print(f"[LinkedIn] Error navegando: {e}")
                
            human_delay(2, 4)
            
            print(f"[LinkedIn] Iniciando Loop JS. Meta: {target_count}")
            
            # Variables de control
            extracted_count = 0
            scroll_attempts = 0
            MAX_SCROLLS = target_count * 3
            consecutive_zero_results = 0

            while extracted_count < target_count and scroll_attempts < MAX_SCROLLS:
                
                # SCRIPT JS DE EXTRACCIÓN Y SCROLL
                js_script = """
                () => {
                    const data = [];
                    
                    // ESTRATEGIA DE SELECTORES ROBUSTOS (DATA ATTRIBUTES)
                    // Las clases cambian (ej: _918fcd8d), pero los data-view-name suelen ser estables.
                    const chunks = document.querySelectorAll('div[data-view-name="feed-full-update"], [role="listitem"], div.feed-shared-update-v2, div.occludable-update, div.artdeco-card');
                    
                    console.log("[JS Debug] Found " + chunks.length + " potential chunks");

                    chunks.forEach(el => {
                        // Ignorar elementos ocultos/vacios
                        if (el.innerText.length < 5) return;

                        let text = "";
                        
                        // Selector de texto prioritario: data-testid="expandable-text-box" (visto en dump)
                        const textNode = el.querySelector('[data-testid="expandable-text-box"]');
                        if (textNode) {
                            text = textNode.innerText;
                        } else {
                            // Fallbacks
                            const specificDiv = el.querySelector('.update-components-text, .feed-shared-text, .comments-comment-item__main-content, .break-words, span[dir="ltr"]');
                            if (specificDiv) {
                                text = specificDiv.innerText;
                            } else {
                                text = el.innerText;
                            }
                        }
                        
                        
                        if (!text) return;
                        text = text.trim();
                        
                        // LOG INTENSIVE DEBUGGING
                        // console.log("Text found: " + text.substring(0, 50));

                        // Filtros básicos JS relaxados para debug
                        if (text.length < 5) return; 
                        
                        // Filtros de UI/Basura
                        if (text.toLowerCase().includes("descriptions off")) return;
                        if (text.toLowerCase().includes("subtitles")) return;
                        if (text === "default, selected") return;

                        // Autor
                        let author = "Desconocido";
                        const authLink = el.querySelector('.app-aware-link, .comments-comment-meta__description-title, .update-components-actor__name, .actor-name');
                        if (authLink) {
                            try {
                                author = authLink.innerText.split('\\n')[0].trim();
                            } catch(e) {}
                        }
                        
                        // Scroll interno
                        el.scrollIntoView({behavior: "smooth", block: "center"});

                        data.push({
                            author: author,
                            content: text,
                        });
                    });
                    
                    // INTENTO DE SCROLL ROBUSTO
                    window.scrollBy(0, 1000);
                    
                    // Si window scroll no funciona, intenta buscar el container de resultados y scrollearlo
                    const searchContainer = document.querySelector('.search-results-container, .scaffold-layout__main');
                    if (searchContainer) {
                         searchContainer.scrollBy(0, 1000);
                    }

                    return { items: data, docHeight: document.body.scrollHeight };
                }
                """
                
                try:
                    # Ejecutar JS
                    result_obj = page.evaluate(js_script)
                    candidates = result_obj.get("items", [])
                    
                    # print(f"[LinkedIn DEBUG] Scroll {scroll_attempts}: JS vio {len(candidates)} items.")
                    
                    added_in_chunk = 0
                    for c in candidates:
                        if extracted_count >= target_count:
                            break
                        
                        clean_text = c['content'].replace("\n", " | ")
                        preview = clean_text[:80] + "..." if len(clean_text) > 80 else clean_text
                        
                        if not any(r['content'] == clean_text for r in results):
                           results.append({
                               "source": "LinkedIn",
                               "type": "post",
                               "author": c['author'],
                               "content": clean_text,
                               "urn": f"lid_{random.randint(100000,999999)}"
                           })
                           extracted_count += 1
                           added_in_chunk += 1
                           # print(f"   -> [NUEVO] {c['author']}: {preview}")
                    
                    if added_in_chunk == 0:
                        consecutive_zero_results += 1
                        print("   (Sin nuevos posts...)")
                    else:
                        consecutive_zero_results = 0

                except Exception as e:
                    print(f"[LinkedIn] Error en evaluate JS: {e}")

                if extracted_count >= target_count:
                    break
                
                # Scroll EXTERNO para asegurar (usando window scroll además del scrollIntoView interno)
                print("[LinkedIn] Forzando Scroll JS...")
                page.evaluate("window.scrollBy(0, 800);")
                time.sleep(3)
                
                scroll_attempts += 1
            
            print(f"[LinkedIn] Finalizado. Total: {len(results)}")
            
        except Exception as e:
            print(f"[LinkedIn] Error FATAL Global: {e}")
        finally:
            try:
                browser.close()
            except:
                pass
                
    return results
