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
    
    user_data_dir = os.path.join(os.getcwd(), "profiles", "auth_profile_linkedin")
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    with sync_playwright() as p:
        print(f"[LinkedIn] Usando perfil en: {user_data_dir}")
        args_list = ["--disable-notifications", "--disable-blink-features=AutomationControlled", "--start-maximized", "--no-sandbox", "--disable-gpu"]
        
        try:
            browser = p.chromium.launch_persistent_context(user_data_dir, headless=True, args=args_list, user_agent=user_agent, viewport=None)
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
            
            total_posts_extracted = 0
            
            while total_posts_extracted < target_count and scroll_attempts_without_new < 15:
                
                print(f"[LinkedIn] Escaneando... (Posts procesados: {total_posts_extracted}/{target_count})")
                
                found_posts = []
                # Filtro regex más amplio para asegurar que detectamos el botón
                action_btns = page.locator('button').filter(has_text=re.compile(r"comentar|comment", re.IGNORECASE))
                
                # Aumentamos el límite de posts por pasada para no quedarnos cortos
                count = action_btns.count()
                for i in range(count):
                    if len(found_posts) > 12: break # Antes 6, subimos a 12
                    try:
                        b = action_btns.nth(i)
                        if b.is_visible():
                            # Subir al post container
                            p_cont = b
                            for _ in range(5): 
                                p_cont = p_cont.locator("..")
                                if p_cont.inner_text().count("\n") > 3: 
                                    found_posts.append((p_cont, b)) 
                                    break
                    except: continue

                new_in_pass = 0
                
                for post_item, action_btn in found_posts:
                    if total_posts_extracted >= target_count: break
                    
                    try:
                        # 1. Chequeo duplicados
                        try:
                            # Tomamos más texto para el hash para evitar falsos positivos por timestamp
                            full_text_hash = post_item.inner_text(timeout=500)
                            # Quitamos números y tiempos relativos para el hash estable
                            stable_text = re.sub(r'\d+', '', full_text_hash[:150])
                        except:
                            continue 
                            
                        phash = hash(stable_text)
                        if phash in processed_ids: 
                            continue 
                        
                        # 2. Focus y Scroll suave para asegurar que carga
                        try:
                             post_item.scroll_into_view_if_needed()
                             # Pequeño scroll adicional para centrar
                             page.mouse.wheel(0, 100)
                             human_delay(0.5, 1)
                        except: pass
                        
                        processed_ids.add(phash)
                        
                        # -- Autor y Post
                        full_txt = post_item.inner_text()
                        lines = full_txt.split('\n')
                        author = "Desconocido"
                        for l in lines:
                            l = l.strip()
                            # Filtros nombre autor
                            if len(l) > 2 and "Publicación" not in l and "seguidores" not in l and "minutos" not in l and "horas" not in l and "relevantes" not in l.lower() and "relevant" not in l.lower():
                                author = l
                                break
                        
                        # Limpieza profunda del Post
                        raw_text = full_txt
                        
                        # 1. Cortar pie de página (Botones de acción)
                        # Intentamos varios splitters comunes
                        for splitter in ["Recomendar", "recomendar", "Like", "Gostar"]:
                            if splitter in raw_text:
                                raw_text = raw_text.split(splitter)[0]
                                break
                        
                        # 2. Cortar Cabecera (Bio, Tiempo, Botón Seguir)
                        header_cut = False
                        if "Seguir" in raw_text[:800]:
                            parts = raw_text.split("Seguir", 1)
                            if len(parts) > 1: raw_text = parts[1]; header_cut = True
                        elif "Follow" in raw_text[:800]:
                            parts = raw_text.split("Follow", 1)
                            if len(parts) > 1: raw_text = parts[1]; header_cut = True
                        
                        # Fallback: Si no cortamos por "Seguir", usamos Regex de tiempo (Ej: "5 d •", "23 h •", "1 sem •")
                        if not header_cut:
                            # Busca patrón: digitos + espacios + (d/h/m/s/sem/yr) + espacios + opcional(•)
                            # Ejemplos que atrapa: "5 días", "2 h", "1 semana •"
                            match = re.search(r'\b\d+\s+(días|dí|d|h|HORAS|m|min|minutos|sem|semanas|w|y|año|años)\s*•?', raw_text[:800], re.IGNORECASE)
                            if match:
                                # Cortamos justo después del match
                                raw_text = raw_text[match.end():]
                                header_cut = True

                        # 3. Limpieza de frases basura específicas
                        replacements = [
                            ("Publicación en el feed", ""), ("Post in feed", ""),
                            ("Mostrar traducción", ""), ("Show translation", ""),
                            ("… más", ""), ("... more", ""), ("… ver más", ""),
                            ("Estado del botón de reacción:", ""),
                            ("Editado", ""), ("Edited", "")
                        ]
                        for old, new in replacements:
                            raw_text = raw_text.replace(old, new)

                        post_clean = raw_text.replace("\n", " ").strip()
                        
                        # 4. Limpieza final: Si empieza con el nombre del autor (residuo), lo quitamos
                        if post_clean.startswith(author):
                            post_clean = post_clean[len(author):].strip()
                        
                        # Limpieza extra de UI (Filtros anteriores)
                        
                        # Limpieza extra de UI (Filtros anteriores)
                        if post_clean.startswith("Más relevantes"): post_clean = post_clean.replace("Más relevantes", "", 1).strip()
                        if post_clean.startswith("Most relevant"): post_clean = post_clean.replace("Most relevant", "", 1).strip()
                        
                        # Guardar Post (Fila Padre)
                        results.append({
                            "platform": "LinkedIn",
                            "post_author": author[:50], 
                            "post_content": post_clean,
                            "comment_author": "",
                            "comment_content": ""
                        })
                        new_in_pass += 1
                        total_posts_extracted += 1 # Contamos POSTS
                        print(f"[LinkedIn] > Post: {author[:20]} ({total_posts_extracted}/{target_count})")

                        # -- APERTURA DE COMENTARIOS --
                        comments_opened = False
                        try:
                            # Intentar botones explícitos de conteo
                            count_btns = post_item.locator('button, a, span').filter(
                                has_text=re.compile(r"\d+\s+(coment|comment|resposta|reply)", re.IGNORECASE)
                            )
                            
                            # Si hay varios, el último suele ser el del footer del post (no de un comentario previo)
                            if count_btns.count() > 0:
                                target_btn = count_btns.last
                                if target_btn.is_visible():
                                    print("   [Action] Abriendo comentarios (botón recuento)...")
                                    target_btn.click(force=True)
                                    comments_opened = True
                                    time.sleep(3)
                            
                            # Si no se abrieron, intentar botón de acción principal
                            if not comments_opened and action_btn.is_visible():
                                # print("   [Action] Tapping 'Comentar' para desplegar...")
                                action_btn.click(force=True)
                                comments_opened = True
                                time.sleep(3)
                                
                        except Exception as e:
                            pass
                        
                        # Cargar más (Botoneras de paginación de comentarios) - REFUGIO MÁS AGRESIVO
                        try:
                            # Intentamos hasta 10 veces expandir comentarios (antes era 3)
                            for _ in range(5): # Pasadas de expansión
                                more_btns = post_item.locator('button').filter(
                                    has_text=re.compile(r"ver\s+más|load\s+more|mostrar\s+más|show\s+more|anteriores|previous", re.IGNORECASE)
                                )
                                count_m = more_btns.count()
                                if count_m == 0: break
                                
                                # Clickar todos los visibles
                                clicked_any = False
                                for mb_idx in range(count_m):
                                    mb = more_btns.nth(mb_idx)
                                    if mb.is_visible():
                                        mb.click(force=True)
                                        clicked_any = True
                                        time.sleep(0.5)
                                
                                if not clicked_any: break
                                time.sleep(1.5) # Esperar carga
                                # Pequeño scroll para activar lazy load
                                page.mouse.wheel(0, 100)
                        except: pass

                        # -- EXTRACCIÓN VIA JAVASCRIPT REFORZADA --
                        try:
                            time.sleep(2)
                            
                            js_script = r"""
                                () => {
                                    const extracted = [];
                                    const actionKeywords = ['responder', 'reply', 'recomendar', 'like', 'gostar', 'interesante'];
                                    
                                    // Limitamos búsqueda al viewport o contenedor activo para eficiencia
                                    const allElements = document.querySelectorAll('button, .artdeco-button, span.artdeco-button__text, a.artdeco-button');
                                    
                                    allElements.forEach(el => {
                                        const txt = el.innerText.toLowerCase().trim();
                                        if (actionKeywords.some(k => txt.includes(k))) {
                                            
                                            let parent = el.parentElement;
                                            // Subimos niveles buscando bloque de texto
                                            for(let i=0; i<6; i++) {
                                                if (!parent) break;
                                                
                                                // Chequeo rápido de longitud
                                                if (parent.innerText.length > 5 && parent.innerText.length < 1500) {
                                                    let clone = parent.cloneNode(true);
                                                    
                                                    // Limpieza de ruido
                                                    clone.querySelectorAll('button, a, .comments-comment-meta, .feed-shared-actor').forEach(x => x.remove());
                                                    
                                                    let cleanText = clone.innerText.trim();
                                                    
                                                    // Filtros de contenido basura
                                                    if (cleanText.length > 3 && 
                                                        !['responder', 'reply', 'recomendar', 'autor'].includes(cleanText.toLowerCase()) &&
                                                        !cleanText.match(/^\d+\s+reacci/i) && // "1 reacción"
                                                        !cleanText.match(/^\d+[dhms]$/i)      // "1d", "2h"
                                                    ) {
                                                        let lines = cleanText.split('\\n').map(l=>l.trim()).filter(l=>l.length>2);
                                                        let finalC = lines.join(' ');
                                                        
                                                        if (finalC.length > 2 && !extracted.includes(finalC)) {
                                                            extracted.push(finalC);
                                                            break; // Encontrado, stop climbing
                                                        }
                                                    }
                                                }
                                                parent = parent.parentElement;
                                            }
                                        }
                                    });
                                    return extracted;
                                }
                            """
                            
                            found_texts = []
                            try: found_texts = page.evaluate(js_script) 
                            except: pass

                            comments_found_now = 0
                            for txt in found_texts:
                                clean = txt.replace("\n", " ").strip()
                                
                                # Filtros Python adicionales
                                if len(clean) < 3: continue
                                if clean in post_clean or post_clean in clean: continue
                                if author in clean and len(clean) < len(author) + 10: continue
                                if "Publicación" in clean and "feed" in clean: continue
                                
                                # Check duplicados ya existentes
                                is_dup = False
                                for r in results:
                                    c_existing = r.get('comment_content', '')
                                    if c_existing and (c_existing == clean or (len(clean) > 15 and clean in c_existing)): 
                                        is_dup = True; break
                                
                                if not is_dup:
                                    # Guardar Comentario con CONTEXTO del Post padre
                                    results.append({
                                        "platform": "LinkedIn",
                                        "post_author": author[:50], # Autor del post original
                                        "post_content": post_clean,
                                        "comment_author": "LinkedIn User", 
                                        "comment_content": clean
                                    })
                                    comments_found_now += 1
                                    
                            if comments_found_now > 0:
                                print(f"   [LinkedIn] + {comments_found_now} comentarios extraídos.")

                        except Exception as e:
                            pass
                    
                    except Exception as e:
                        pass
                
                # --- SCROLL HACIA ABAJO FINAL ---
                print("[LinkedIn] Buscando más posts...")
                page.mouse.wheel(0, 800) # Scroll mouse más natural
                time.sleep(0.5)
                page.keyboard.press("PageDown") # Combo con teclado
                time.sleep(2)
                
                # Chequeo de fin simple
                try:
                    if page.locator("p.artdeco-empty-state__message").is_visible(): break
                except: pass
                
                if new_in_pass == 0:
                     scroll_attempts_without_new += 1
                     print(f"[LinkedIn] (Sin nuevos items {scroll_attempts_without_new}/15)")
                     
                     if scroll_attempts_without_new > 2:
                         # Intento de desbloqueo agresivo
                         print("   [Action] Desbloqueando feed con scroll...")
                         page.evaluate("window.scrollBy(0, -500)")
                         time.sleep(1)
                         page.evaluate("window.scrollBy(0, 1500)") 
                         time.sleep(2)
                else:
                    scroll_attempts_without_new = 0

                # Paginación "Ver más resultados"
                try:
                    if scroll_attempts_without_new > 4:
                        next_btn = page.locator('button.artdeco-pagination__button--next')
                        if next_btn.is_visible():
                            next_btn.click()
                            scroll_attempts_without_new = 0
                            time.sleep(3)
                except: pass

            print(f"[LinkedIn] Finalizado. Total: {len(results)}")
            
        except Exception as e:
            print(f"[LinkedIn] Error Global: {e}")
        finally:
            try: browser.close()
            except: pass
                
    return results
