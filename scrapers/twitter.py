from playwright.sync_api import sync_playwright
import time

def scrape_twitter(topic, username, password):
    results = []
    print(f"[X/Twitter] Iniciando hilo para: {topic}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale='es-ES')
        page = context.new_page()

        try:
            # 1. Login
            page.goto("https://x.com/i/flow/login")
            time.sleep(4)
            
            # Username
            if page.locator("input[autocomplete='username']").count() > 0:
                print(f"[X] Introduciendo usuario...")
                page.fill("input[autocomplete='username']", username)
                page.click("button:has-text('Siguiente')") # O next
                time.sleep(2)
            
            # Password
            if page.locator("input[name='password']").count() > 0:
                print(f"[X] Introduciendo password...")
                page.fill("input[name='password']", password)
                page.click("button[data-testid='LoginForm_Login_Button']")
                time.sleep(5)

            # 2. Búsqueda
            print(f"[X] Buscando '{topic}'...")
            page.goto(f"https://x.com/search?q={topic}&src=typed_query&f=live")
            time.sleep(5)
            
            # 3. Extracción
            tweets = page.locator('article[data-testid="tweet"]')
            count = tweets.count()
            if count == 0:
                page.mouse.wheel(0, 1000)
                time.sleep(2)
                tweets = page.locator('article[data-testid="tweet"]')
                count = tweets.count()

            print(f"[X] Se encontraron {count} tweets.")
            
            for i in range(min(10, count)):
                try:
                    text_div = tweets.nth(i).locator('div[data-testid="tweetText"]')
                    if text_div.count() > 0:
                        results.append({"source": "Twitter", "content": text_div.inner_text()})
                except:
                    pass

        except Exception as e:
            print(f"[X] Error: {e}")
        finally:
            browser.close()
            
    return results
