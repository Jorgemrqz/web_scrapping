import pandas as pd
import json
import os

topic = "Venezuela"
json_filename = f"data/corpus_{topic}.json"
csv_filename = f"data/corpus_{topic}.csv"

if os.path.exists(json_filename):
    with open(json_filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Reordenar columnas
    desired_order = ["platform", "post_index", "post_author", "post_content", "comment_author", "comment_content"]
    final_cols = [c for c in desired_order if c in df.columns]
    final_cols += [c for c in df.columns if c not in final_cols]
    df = df[final_cols]
    
    # Limpieza
    try:
        df = df.map(lambda x: x.encode('unicode_escape').decode('utf-8') if isinstance(x, str) else x)
    except AttributeError:
        df = df.applymap(lambda x: x.encode('unicode_escape').decode('utf-8') if isinstance(x, str) else x)
        
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    print(f"Convertido {json_filename} -> {csv_filename}")
else:
    print("No se encontró el JSON")
