import os
import pandas as pd
from llm_processor import process_dataframe_concurrently

def analyze_existing_csv(filename):
    """
    Carga un CSV existente, lo pasa por el procesador de LLMs y guarda el resultado.
    """
    input_path = os.path.join("data", filename)
    
    if not os.path.exists(input_path):
        print(f"[Error] No se encontró el archivo: {input_path}")
        return

    print(f"[Info] Cargando {input_path}...")
    try:
        # Intentar leer con detección de separador flexible
        try:
            df = pd.read_csv(input_path, sep=',', encoding='utf-8')
            if len(df.columns) < 2:
                 df = pd.read_csv(input_path, sep=';', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(input_path, sep=',', encoding='latin1')

        print(f"[Info] Dataset cargado: {len(df)} filas.")
        
        # Limpieza básica de columnas previas si ya existen
        if 'sentiment_llm' in df.columns:
            print("[Info] El dataset ya tiene columnas de LLM. Se sobrescribirán.")
            df = df.drop(columns=['sentiment_llm', 'explanation_llm'], errors='ignore')

        # Procesar
        print(f"[Info] Iniciando análisis con LLMs para {len(df)} registros...")
        df_analyzed = process_dataframe_concurrently(df)
        
        # Guardar resultado
        output_filename = filename.replace(".csv", "_analyzed.csv")
        output_path = os.path.join("data", output_filename)
        
        # Reordenar columnas para poner sentimientos al principio (útil para revisar)
        cols = list(df_analyzed.columns)
        new_order = ['platform', 'sentiment_llm', 'explanation_llm'] + [c for c in cols if c not in ['platform', 'sentiment_llm', 'explanation_llm']]
        df_analyzed = df_analyzed[new_order]
        
        df_analyzed.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[Exito] Análisis completado.")
        print(f"        Archivo guardado en: {output_path}")
        
    except Exception as e:
        print(f"[Fatal] Error procesando el CSV: {e}")

if __name__ == "__main__":
    # Nombre del archivo a procesar
    TARGET_FILE = "corpus_Nicolas Muñoz_raw.csv" 
    
    analyze_existing_csv(TARGET_FILE)
