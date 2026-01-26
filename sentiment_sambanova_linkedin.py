import os
import glob
import pandas as pd
import time
from tqdm import tqdm
import config
from sambanova import SambaNova

def load_linkedin_data(data_dir="data"):
    all_posts = []
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    print(f"[Samba-LinkedIn] Buscando archivos de LinkedIn en {data_dir}")
    
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            if 'text' in df.columns and 'content' not in df.columns:
                df['content'] = df['text']
            
            # Heurística LinkedIn
            is_li = False
            if 'linkedin' in file.lower():
                is_li = True
            elif 'source' in df.columns:
                if df['source'].str.contains('LinkedIn', case=False, na=False).any():
                    is_li = True
            
            if is_li and 'content' in df.columns:
                data = df.to_dict(orient='records')
                for d in data:
                    d['source_file'] = os.path.basename(file)
                    d['content'] = str(d.get('content', '')).strip()
                    d['source'] = 'LinkedIn'
                all_posts.extend(data)
                
        except Exception as e:
            print(f"[Samba-LinkedIn] Error leyendo {file}: {e}")
            
    print(f"[Samba-LinkedIn] Total de registros LinkedIn cargados: {len(all_posts)}")
    return all_posts

def configure_sambanova():
    api_key = getattr(config, "SAMBANOVA_API_KEY", None)
    if not api_key:
        print("Error: SAMBANOVA_API_KEY no en config.py")
        return None
    return SambaNova(api_key=api_key)

def analyze_sentiment(client, text):
    if not text or len(text) < 3: return "Neutral"

    prompt = f"""
    Clasifica el siguiente comentario de LinkedIn en: Positivo, Negativo, Neutral.
    Comentario: "{text}"
    Respuesta (solo una palabra):
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role":"user", "content": prompt}],
            model="ALLaM-7B-Instruct-preview",
            temperature=0.0,
            max_completion_tokens=5
        )
        res = completion.choices[0].message.content.strip().replace(".", "")
        if "Positivo" in res: return "Positivo"
        if "Negativo" in res: return "Negativo"
        return "Neutral"
    except Exception as e:
        print(f"Error: {e}")
        return "Error"

def run_analysis():
    client = configure_sambanova()
    if not client: return

    posts = load_linkedin_data()
    if not posts:
        print("No se encontraron posts de LinkedIn.")
        return

    results = []
    print(f"Analizando {len(posts)} comentarios con SambaNova...")
    
    for post in tqdm(posts):
        sentiment = analyze_sentiment(client, post.get('content',''))
        post['sentiment'] = sentiment
        results.append(post)
        time.sleep(0.5) 

    output_file = "data/sentiment_sambanova_linkedin.csv"
    pd.DataFrame(results).to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"Resultados guardados en {output_file}")
    
    print(pd.DataFrame(results)['sentiment'].value_counts())

if __name__ == "__main__":
    run_analysis()
