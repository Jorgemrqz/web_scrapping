import pandas as pd
import json
import os
from llm_processor import LLMProcessor

def perform_analysis(csv_path, topic, df=None, timings=None):
    """
    Lee el DF (o CSV/JSON), calcula estadísticas de sentimiento
    y genera el storytelling con DeepSeek.
    Guarda los resultados en un JSON 'analysis_{topic}.json'.
    """
    if df is None:
        if csv_path and os.path.exists(csv_path):
             try:
                df = pd.read_csv(csv_path)
             except Exception as e:
                return {"error": f"Failed to read CSV: {e}"}
        else:
             # Try JSON if CSV not found (future compatibility)
             json_path = csv_path.replace('.csv', '.json') if csv_path else None
             if json_path and os.path.exists(json_path):
                 try:
                     with open(json_path, 'r', encoding='utf-8') as f:
                         data = json.load(f)
                     # Flatten for analysis if needed, or handle structured
                     # For now, let's assume we need to rebuild the flat DF for the logic below
                     # This is a bit complex, so we prefer passing DF directly from main
                     pass 
                 except:
                     pass
                     
        if df is None:
            return {"error": "No data available (DataFrame is None and file not found)"}

    # Normalizar columnas por si acaso
    if 'sentiment_llm' not in df.columns:
        return {"error": "Column 'sentiment_llm' missing. Run LLM phase first."}

    # 1. Estadísticas Globales
    global_counts = df['sentiment_llm'].value_counts().to_dict()
    total = len(df)
    global_stats = {k: int(v) for k,v in global_counts.items()}
    global_percents = {k: f"{(v/total)*100:.1f}%" for k,v in global_stats.items()}

    # 2. Estadísticas por Red Social
    by_platform = {}
    if 'platform' in df.columns:
        # Normalizar nombres de plataforma
        df['platform_norm'] = df['platform'].astype(str).str.lower().str.strip()
        
        platforms = df['platform_norm'].unique()
        for p in platforms:
            sub = df[df['platform_norm'] == p]
            counts = sub['sentiment_llm'].value_counts().to_dict()
            by_platform[p] = {k: int(v) for k,v in counts.items()}

    # 3. Ejemplos (para contexto del LLM)
    # Tomamos muestras aleatorias de comentarios positivos/negativos
    pos_examples = df[df['sentiment_llm'].str.lower().str.contains("positivo", na=False)]['post_content'].dropna().head(3).tolist()
    neg_examples = df[df['sentiment_llm'].str.lower().str.contains("negativo", na=False)]['post_content'].dropna().head(3).tolist()

    # Preparamos el objeto de datos para el LLM
    stats_package = {
        "global_counts": global_stats,
        "global_percents": global_percents,
        "by_platform": by_platform,
        "examples_positive": pos_examples,
        "examples_negative": neg_examples
    }

    # 4. Generar Storytelling
    print(f"[Analysis] Generando narrativa para: {topic}...")
    processor = LLMProcessor()
    story = processor.generate_storytelling(topic, stats_package)

    # 5. Estructura Final para el Frontend
    
    # Intentar cargar datos estructurados desde MongoDB
    # (Ya que main_parallel los guardó ahí, no en disco)
    structured_data = []
    
    try:
        from database import Database
        db = Database()
        if db.is_connected:
            raw_data = db.get_historical_data(topic)
            if raw_data:
                structured_data = raw_data
                print(f"[Analysis] Recuperados {len(structured_data)} registros estructurados desde MongoDB.")
            else:
                print(f"[Analysis] No se encontraron registros en MongoDB para '{topic}'. Usando DataFrame plano.")
                structured_data = df.head(100).to_dict(orient="records")
        else:
             structured_data = df.head(100).to_dict(orient="records")
    except Exception as e:
        print(f"[Analysis Error] Consultando MongoDB: {e}")
        structured_data = df.head(100).to_dict(orient="records")

    final_output = {
        "topic": topic,
        "total_posts": total,
        "stats": stats_package,
        "storytelling": story,
        "timings": timings, # Duraciones de ejecución
        "data_preview": structured_data # Ahora enviamos la lista recuperada de Mongo
    }

    # Guardar Análisis en MongoDB
    try:
        if db.is_connected:
            db.save_analysis(topic, final_output)
        else:
            print("[Error] No se pudo guardar el análisis en MongoDB por falta de conexión.")
    except Exception as e:
         print(f"[Analysis Error] Fallo al guardar en MongoDB: {e}")

    # Fallback: Guardar JSON local? El usuario dijo "todo dejalo en mongo".
    # Pero el API sigue leyendo de disco local en `api.py`.
    # Si queremos respetar estrictamente, no guardamos en disco.
    # PERO, el frontend (api.py) necesita ser actualizado para leer de Mongo también.
    
    # Por ahora, guardamos localMENTE también para asegurar compatibilidad mientras actualizamos api.py, 
    # pero el usuario pidió "ya no guardes en data".
    # Así que COMENTAMOS el guardado local.
    
    # output_json = f"data/analysis_{topic}.json"
    # with open(output_json, 'w', encoding='utf-8') as f:
    #     json.dump(final_output, f, indent=4, ensure_ascii=False)
    # print(f"[Analysis] Reporte guardado en: {output_json}")
    
    return final_output
