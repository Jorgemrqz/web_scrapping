import pandas as pd
import json
import os
from llm_processor import LLMProcessor

def perform_analysis(csv_path, topic):
    """
    Lee el CSV procesado, calcula estadísticas de sentimiento
    y genera el storytelling con DeepSeek.
    Guarda los resultados en un JSON 'analysis_{topic}.json'.
    """
    if not os.path.exists(csv_path):
        return {"error": "CSV file not found"}

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return {"error": f"Failed to read CSV: {e}"}

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
    final_output = {
        "topic": topic,
        "total_posts": total,
        "stats": stats_package,
        "storytelling": story,
        "data_preview": df.head(10).to_dict(orient="records") # Para mostrar tabla rápida
    }

    # Guardar JSON
    output_json = f"data/analysis_{topic}.json"
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)
    
    print(f"[Analysis] Reporte guardado en: {output_json}")
    return final_output
