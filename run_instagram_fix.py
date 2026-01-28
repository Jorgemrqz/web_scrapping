import pandas as pd
import os
from tqdm import tqdm
from llm_processor import LLMProcessor
from concurrent.futures import ThreadPoolExecutor

def main():
    # Rutas
    data_dir = "data"
    # Trabajamos sobre el archivo YA analizado para corregir los errores
    target_file = "corpus_Venezuela_analyzed.csv"
    file_path = os.path.join(data_dir, target_file)

    if not os.path.exists(file_path):
        print(f"No se encontró el archivo: {file_path}")
        return

    print(f"Cargando datos desde: {file_path}")
    df = pd.read_csv(file_path)
    
    # Instanciamos el procesador (que ya tiene el fix de Gemini 2.5)
    processor = LLMProcessor()

    # Identificar filas de INSTAGRAM que necesitan arreglo
    # Criterio: Platform/Source es Instagram Y (Sentiment es Error/Nulo O Explanation tiene '404')
    indices_to_fix = []
    
    for idx, row in df.iterrows():
        # Detección de Instagram (flexible)
        platform = str(row.get('platform', '')).lower()
        source = str(row.get('source', '')).lower()
        is_instagram = 'instagram' in platform or 'instagram' in source
        
        if not is_instagram:
            continue
            
        # Analisis de estado
        val = row.get('sentiment_llm')
        expl = str(row.get('explanation_llm', ''))
        
        needs_fix = False
        if pd.isna(val) or val == "" or val == "N/A":
            needs_fix = True
        elif val == "Error":
            needs_fix = True
        elif "404" in expl or "error" in expl.lower():
            needs_fix = True
            
        if needs_fix:
            indices_to_fix.append(idx)

    print(f"Total filas: {len(df)}")
    print(f"Filas de INSTAGRAM a reparar: {len(indices_to_fix)}")

    if not indices_to_fix:
        print("¡No hay nada que reparar en Instagram! Todo parece estar bien.")
        return

    # Función helper para procesar
    import time
    def process_ig_row(idx):
        row = df.iloc[idx]
        # Construir contenido
        p_content = str(row.get('post_content', ''))
        c_content = str(row.get('comment_content', ''))
        
        if not p_content and not c_content:
             content = str(row.get('content', ''))
        else:
             content = f"Post: {p_content} | Comment: {c_content}"

        # Llamar DIRECTAMENTE a Llama (Groq)
        result = processor.analyze_with_llama(content[:800])
        
        # Groq es muy rápido y tiene límites altos, pero dejamos una pequeña pausa de seguridad
        # time.sleep(1) # Pausa mínima opcional
        
        return idx, result

    print("Iniciando reparación de Instagram con Llama 3 (Groq en paralelo)...")
    
    # Ejecutar EN PARALELO (Workers=10) - Groq es rápido
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(tqdm(executor.map(process_ig_row, indices_to_fix), total=len(indices_to_fix), unit="fix"))
    
    # Guardar resultados en el DataFrame
    success_count = 0
    for idx, res in results:
        df.at[idx, 'sentiment_llm'] = res.get('sentiment', 'Error')
        df.at[idx, 'explanation_llm'] = res.get('explanation', '')
        if res.get('sentiment') != 'Error':
            success_count += 1

    print(f"Reparación finalizada. Éxitos: {success_count}/{len(indices_to_fix)}")
    
    # Guardar archivo
    try:
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"Archivo actualizado guardado en: {file_path}")
    except Exception as e:
        print(f"Error guardando el archivo: {e}")

if __name__ == "__main__":
    main()
