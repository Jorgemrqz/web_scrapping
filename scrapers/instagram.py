from playwright.sync_api import sync_playwright
import os
import re
import time
import random
from datetime import datetime
from urllib.parse import quote_plus

POST_RE = re.compile(r"^/(p|reel)/[^/]+/")

def human_delay(min_s=1.2, max_s=2.8):
    time.sleep(random.uniform(min_s, max_s))

def clean_comment(text: str) -> str:
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_comments(page, caption: str = "", max_comments: int = 8):
    patterns = [
        "Ver todos los comentarios", "Ver más comentarios", "View all comments",
        "View all", "Ver los", "Load more comments"
    ]
    for pat in patterns:
        try:
            page.get_by_text(re.compile(pat, re.IGNORECASE)).first.click(timeout=1200)
            page.wait_for_timeout(1200)
            break
        except:
            pass

    try:
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(800)
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(800)
    except:
        pass

    candidates = page.evaluate("""
    () => {
      const root = document.querySelector("main");
      if (!root) return [];

      const spans = Array.from(root.querySelectorAll("span"))
        .map(s => (s.innerText || "").trim())
        .filter(t => t.length >= 20);

      const norm = spans.map(t => t.replace(/\\s+/g, " ").trim());

      const seen = new Set();
      const out = [];
      for (const t of norm) {
        if (!seen.has(t)) { seen.add(t); out.push(t); }
      }
      return out;
    }
    """)

    bad_substrings = [
        "me gusta", "likes", "reply", "responder", "respuestas", "replies",
        "ver traducción", "see translation", "ver las", "view all", "view more",
        "agrega un comentario", "add a comment",
        "seguir", "follow"
    ]

    cleaned = []
    cap = (caption or "").strip().lower()
    for t in candidates:
        tt = clean_comment(t)
        low = tt.lower()

        if any(b in low for b in bad_substrings):
            continue

        if cap and cap[:40] and cap[:40] in low:
            continue

        cleaned.append(tt)
        if len(cleaned) >= max_comments:
            break

    return cleaned

def _debug_enabled() -> bool:
    return os.getenv("IG_DEBUG", "").strip() in ("1", "true", "TRUE", "yes", "YES")

def _save_debug(page, hashtag: str, label: str):
    if not _debug_enabled():
        return
    os.makedirs("data", exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-z0-9_]+", "_", hashtag.lower())
    html_path = f"data/debug_instagram_{safe}_{label}_{stamp}.html"
    png_path  = f"data/debug_instagram_{safe}_{label}_{stamp}.png"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page.content())
    page.screenshot(path=png_path, full_page=True)
    print(f"[instagram][debug] HTML: {html_path}")
    print(f"[instagram][debug] PNG : {png_path}")

def _try_login_if_needed(page, username: str, password: str):
    """
    Best-effort: si IG te manda a login y hay credenciales, intenta.
    Si hay 2FA/captcha, lo normal es usar login_manual.py y listo.
    """
    if "/accounts/login" not in page.url:
        return

    print("[instagram] Detecté /accounts/login. Intentando login automático (best-effort)...")
    if not (username and password):
        print("[instagram] No hay credenciales. Usa login_manual.py --site instagram para guardar sesión.")
        return

    try:
        # Selectores típicos (pueden cambiar, por eso best-effort)
        page.wait_for_selector('input[name="username"]', timeout=10000)
        page.fill('input[name="username"]', username)
        human_delay()
        page.fill('input[name="password"]', password)
        human_delay()
        # botón submit
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"[instagram] No pude completar login automático: {e}")

def scrape_instagram(topic: str, username: str, password: str, target_count: int = 10):
    """
    Interfaz compatible con main_parallel.worker:
    - topic: string del tema (se interpreta como hashtag)
    - username/password: opcionales (preferible sesión persistente)
    - target_count: número objetivo de posts
    """
    # Perfil persistente igual que LinkedIn
    user_data_dir = os.path.join(os.getcwd(), "auth_profile_instagram")
    os.makedirs(user_data_dir, exist_ok=True)

    hashtag = topic.strip().lstrip("#").replace(" ", "").lower()
    if not hashtag:
        print("[instagram] Topic vacío. Abortando.")
        return []

    start_url = f"https://www.instagram.com/explore/tags/{quote_plus(hashtag)}/"
    results = []

    with sync_playwright() as p:
        args = [
            "--start-maximized",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ]

        ctx = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,           # mantener consistente con el proyecto
            args=args,
            viewport=None,
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)

        print(f"[instagram] Abriendo hashtag: #{hashtag}")
        try:
            page.goto(start_url, wait_until="domcontentloaded")
        except Exception as e:
            print(f"[instagram] Error navegando a hashtag: {e}")
            ctx.close()
            return []

        page.wait_for_timeout(4000)
        print(f"[instagram] URL actual: {page.url}")
        _save_debug(page, hashtag, "hashtag_loaded")

        # Si redirige a login, intentar (best-effort), sino pedir login_manual
        _try_login_if_needed(page, username, password)
        if "/accounts/login" in page.url:
            _save_debug(page, hashtag, "still_on_login")
            ctx.close()
            print("[instagram] Sigues en login. Ejecuta: python login_manual.py --site instagram")
            return []

        # Cerrar popups comunes
        for name in ["Aceptar", "Permitir todas las cookies", "Allow all cookies", "Not now", "Ahora no"]:
            try:
                page.get_by_role("button", name=name).click(timeout=1500)
            except:
                pass

        # Recolectar URLs de posts
        # MODIFICADO: Buscamos URLs hasta tener suficientes PARA sacar comentarios.
        # Estimamos 5 comentarios por post para no scrollear eternamente, pero el objetivo final es comentarios.
        
        seen = set()
        scrolls = 0
        estimated_posts_needed = max(10, target_count) # Mejor sobrar que faltar
        max_scrolls = 60
        
        print(f"[instagram] Recolectando links para intentar llegar a {target_count} comentarios...")

        while len(seen) < estimated_posts_needed and scrolls < max_scrolls:
            hrefs = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href'))""")
            new_count = 0
            for href in hrefs:
                if isinstance(href, str) and POST_RE.match(href):
                    full = "https://www.instagram.com" + href
                    if full not in seen:
                        seen.add(full)
                        new_count += 1

            # print(f"[instagram] scroll={scrolls} links={len(seen)}")

            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1500)
            scrolls += 1
            
            # Si tenemos muchos links, parar early
            if len(seen) > target_count * 1.5: break

        if not seen:
            _save_debug(page, hashtag, "no_links_after_scroll")
            ctx.close()
            print("[instagram] No se detectaron links /p/ o /reel/ en el hashtag.")
            return []

        post_urls = list(seen)
        print(f"[instagram] Se visitarán hasta {len(post_urls)} posts buscando {target_count} comentarios.")

        # Visit posts
        total_comments_collected = 0
        
        for i, post_url in enumerate(post_urls, start=1):
            if total_comments_collected >= target_count: 
                print("[instagram] Meta de comentarios alcanzada.")
                break
                
            try:
                print(f"[instagram] ({total_comments_collected}/{target_count}) Visitando: {post_url}")
                page.goto(post_url, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)

                try:
                    page.wait_for_selector("main", timeout=15000)
                except: pass

                # Caption
                caption = ""
                meta = page.query_selector('meta[property="og:description"]')
                if meta:
                    content = meta.get_attribute("content")
                    if content:
                        caption = content.strip()
                        caption = re.sub(r'^.*?:\s*', '', caption)

                # Extraer Comentarios (Límite aumentado a 50 por post)
                post_comments = extract_comments(page, caption=caption, max_comments=50)

                # Guardar Post (Solo si tiene comentarios o es relevante)
                clean_text = caption.replace("\n", " | ").strip()
                if clean_text:
                    results.append({
                        "source": "Instagram", "type": "post",
                        "author": "Desconocido", "content": clean_text,
                        "url": post_url
                    })

                # Guardar Comentarios
                for comment_text in post_comments:
                    if total_comments_collected >= target_count: break
                    results.append({
                        "source": "Instagram", "type": "comment",
                        "author": "Desconocido", "content": comment_text,
                        "parent_url": post_url
                    })
                    total_comments_collected += 1

                human_delay()

            except Exception as e:
                print(f"[instagram] Error en {post_url}: {e}")

        ctx.close()

    print(f"[instagram] Finalizado. Extraje {total_comments_collected} comentarios.")
    return results
