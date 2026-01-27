from scrapers.linkedin import scrape_linkedin
import config
import csv

if __name__ == "__main__":
    topic = "Venezuela"
    print("Probando LinkedIn Scraper...")
    # creds = config.CREDENTIALS["linkedin"] # No existe en config.py
    email = "" 
    password = ""
    
    # Probar con 50 comentarios
    data = scrape_linkedin(topic, email, password, target_count=50)
    
    print(f"Resultados: {len(data)}")
    if data:
        with open("test_linkedin.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["platform", "post_index", "post_author", "post_content", "comment_author", "comment_content"])
            writer.writeheader()
            writer.writerows(data)
        print("Guardado test_linkedin.csv")
    else:
        print("No se extrajo data.")
