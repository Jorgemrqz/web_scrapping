import os
import glob
import pandas as pd
import time
from tqdm import tqdm
import config
from cerebras.cloud.sdk import Cerebras

def load_x_data(data_dir="data"):
    all_posts = []
    # Buscamos CSVs que parezcan de Twitter/X
    # Patrones comunes: corpus_*.csv pero filtramos contenido interno
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    print(f"[Cerebras-X] Buscando archivos de Twitter/X en {data_dir}")
    
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            if 'text' in df.columns and 'content' not in df.columns:
                df['content'] = df['text']
            
            # Chequeo heurístico de si es Twitter
            is_x = False
            if 'twitter' in file.lower() or '_x_' in file.lower():
                is_x = True
            elif 'source' in df.columns:
                if df['source'].str.contains('Twitter|X', case=False, na=False).any():
                    is_x = True
            
            # Filtro por contenido si no estamos seguros
            if is_x and 'content' in df.columns:
                data = df.to_dict(orient='records')
                for d in data:
                    d['source_file'] = os.path.basename(file)
                    d['content'] = str(d.get('content', '')).strip()
                    # Forzamos etiqueta por si acaso
                    d['source'] = 'Twitter' 
                all_posts.extend(data)
                
        except Exception as e:
            print(f"[Cerebras-X] Error leyendo {file}: {e}")
            
    print(f"[Cerebras-X] Total de registros X cargados: {len(all_posts)}")
    return all_posts

def configure_cerebras():
    api_key = config.CEREBRAS_API_KEY
    if not api_key or "csk-" not in api_key:
        print("Error: CEREBRAS_API_KEY no válida en config.py")
        return None
    return Cerebras(api_key=api_key)

def analyze_sentiment(client, text):
    if not text or len(text) < 3: return "Neutral"

    prompt = f"""
    Clasifica el siguiente tweet en: Positivo, Negativo, Neutral.
    Tweet: "{text}"
    Respuesta (solo una palabra):
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role":"user", "content": prompt}],
            model="llama-3.3-70b",
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
    client = configure_cerebras()
    if not client: return

    posts = load_x_data()
    if not posts:
        print("No se encontraron posts de Twitter/X.")
        return

    results = []
    print(f"Analizando {len(posts)} tweets con Cerebras (Llama 3.3)...")
    
    for post in tqdm(posts):
        sentiment = analyze_sentiment(client, post.get('content',''))
        post['sentiment'] = sentiment
        results.append(post)
        time.sleep(0.3) # Leve pausa

    output_file = "data/sentiment_analysis_cerebras_x.csv"
    pd.DataFrame(results).to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"Resultados guardados en {output_file}")
    
    print(pd.DataFrame(results)['sentiment'].value_counts())

if __name__ == "__main__":
    run_analysis()
