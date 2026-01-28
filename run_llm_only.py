import pandas as pd
import os
import sys
from tqdm import tqdm
from llm_processor import LLMProcessor
from concurrent.futures import ThreadPoolExecutor

def main():
    # Configuración
    data_dir = "data"
    input_file = "corpus_Venezuela.csv"
    output_file = "corpus_Venezuela_analyzed.csv"
    
    input_path = os.path.join(data_dir, input_file)
    output_path = os.path.join(data_dir, output_file)

    if not os.path.exists(input_path):
        print(f"No se encontró el archivo de entrada: {input_path}")
        return

    print(f"Cargando datos originales desde: {input_path}")
    df_input = pd.read_csv(input_path)
    total_rows = len(df_input)

    # Cargar progreso previo si existe
    if os.path.exists(output_path):
        print(f"Encontrado archivo de salida previo: {output_path}")
        try:
            df_output = pd.read_csv(output_path)
            # Asegurar que tenga las columnas necesarias
            if 'sentiment_llm' not in df_output.columns:
                df_output['sentiment_llm'] = None
            if 'explanation_llm' not in df_output.columns:
                df_output['explanation_llm'] = None
            
            # Si el output tiene menos filas (o más) que el input, sincronizar o reiniciar
            # Estrategia: Copiar resultados ya hechos al df_input en memoria
            # Asumimos que el orden no ha cambiado.
            if len(df_output) == len(df_input):
                 df_input['sentiment_llm'] = df_output['sentiment_llm']
                 df_input['explanation_llm'] = df_output['explanation_llm']
                 print("Progreso anterior cargado exitosamente.")
            else:
                print("El archivo de salida tiene diferente longitud. Se intentará preservar lo posible por índice.")
                # Merge por índice si es posible, o resetear si es muy complejo
                # Para simplificar y evitar errores: Si no coinciden exacto, mejor procesar lo que falte.
                # Crearemos las columnas vacías
                df_input['sentiment_llm'] = None
                df_input['explanation_llm'] = None
        except Exception as e:
            print(f"Error leyendo archivo previo, se iniciará de cero: {e}")
            df_input['sentiment_llm'] = None
            df_input['explanation_llm'] = None
    else:
        df_input['sentiment_llm'] = None
        df_input['explanation_llm'] = None

    processor = LLMProcessor()
    
    # Identificar filas pendientes
    # Una fila está pendiente si sentiment_llm es nulo (NaN) o es 'Error'
    # Opcional: Si quieres reintentar errores, inclúyelos. Si solo nulos, fíltralo.
    # Aquí procesaremos las que sean Nulas o vacías.
    
    # Identificar filas pendientes o con errores/data incompleta
    def needs_processing(row):
        val = row.get('sentiment_llm')
        expl = str(row.get('explanation_llm', ''))
        
        # 1. No procesado
        if pd.isna(val) or val == "" or val == "N/A": return True
        # 2. Error explícito
        if val == "Error": return True
        # 3. Caso LinkedIn (Nan por problema de columnas)
        if "nan" in expl.lower() or "no contiene contenido" in expl.lower(): return True
        # 4. Caso Error API en explicación (Ej: 404 models)
        if "404" in expl or "error" in expl.lower(): return True
        
        return False

    indices_to_process = [
        i for i, row in df_input.iterrows() 
        if needs_processing(row)
    ]
    
    print(f"Registros totales: {total_rows}")
    print(f"Registros pendientes por procesar: {len(indices_to_process)}")
    
    if len(indices_to_process) == 0:
        print("Todo está procesado. ¡Listo!")
        return

    # Función wrapper para procesar y devolver índice
    def process_wrapper(idx_row_tuple):
        idx, row = idx_row_tuple
        result = processor.analyze_row(row)
        return idx, result

    # Lista de tuplas (índice, fila) solo de las pendientes
    rows_to_process = [(i, df_input.iloc[i]) for i in indices_to_process]

    print("Iniciando procesamiento incremental con autoguardado...")
    batch_size = 10 # Guardar cada 10 filas
    results_buffer = []
    
    with ThreadPoolExecutor(max_workers=2) as executor: # Reducido a 2 para evitar Rate Limit de Groq
        # Usamos tqdm
        iterator = tqdm(executor.map(process_wrapper, rows_to_process), total=len(rows_to_process), unit="posts")
        
        for i, (idx, res) in enumerate(iterator):
            # Actualizar DataFrame en memoria
            df_input.at[idx, 'sentiment_llm'] = res.get('sentiment', 'Error')
            df_input.at[idx, 'explanation_llm'] = res.get('explanation', '')
            
            # Guardado periódico
            if (i + 1) % batch_size == 0:
                try:
                    df_input.to_csv(output_path, index=False, encoding='utf-8-sig')
                    # iterator.set_description("Guardado parcial")
                except Exception as e:
                    print(f"\nError guardando parcial: {e}")

    # Guardado final
    try:
        df_input.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[Terminado] Archivo completo guardado en: {output_path}")
    except Exception as e:
        print(f"Error guardando final: {e}")

if __name__ == "__main__":
    main()
