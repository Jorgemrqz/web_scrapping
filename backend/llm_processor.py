import os
import json
import pandas as pd
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Importar claves desde config
try:
    from config import DEEPSEEK_API_KEY
except ImportError:
    DEEPSEEK_API_KEY = ""

class LLMProcessor:
    def __init__(self):
        self.system_prompt = (
            "Eres un analista de sentimientos experto. "
            "Tu tarea es clasificar el siguiente texto de una red social. "
            "Responde SOLAMENTE un objeto JSON con dos claves: "
            "'sentiment' (Positivo, Negativo, Neutro) y 'explanation' (breve explicación de por qué en español)."
        )

    def _safe_json_parse(self, text):
        try:
            # Limpieza básica por si el LLM devuelve markdown
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            return {"sentiment": "Error", "explanation": "Falló el parsing JSON: " + text[:50]}

    def analyze_with_deepseek(self, text):
        if not DEEPSEEK_API_KEY: return {"sentiment": "N/A", "explanation": "Falta DEEPSEEK_API_KEY"}
        try:
            # DeepSeek es compatible con OpenAI Client
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat", # DeepSeek V3 (Chat)
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Texto: {text}"}
                ],
                temperature=0,
                max_tokens=200 
            )
            
            # Capturar uso de tokens
            usage = response.usage
            total_tokens = usage.total_tokens
            
            result = self._safe_json_parse(response.choices[0].message.content)
            # Inyectar tokens en el resultado
            if isinstance(result, dict):
                result['tokens'] = total_tokens
            return result

        except Exception as e:
            return {"sentiment": "Error", "explanation": str(e), "tokens": 0}

    def generate_storytelling(self, topic, stats):
        """
        Genera un reporte narrativo (storytelling) basado en estadísticas agregadas.
        stats format expected:
        {
            "global": {"Positivo": 10, "Negativo": 5, ...},
            "by_platform": {
                "twitter": {"Positivo": 2, ...},
                ...
            },
            "top_positive_examples": [...],
            "top_negative_examples": [...]
        }
        """
        if not DEEPSEEK_API_KEY: return "Error: No API Key."
        
        prompt = (
            f"Actúa como un analista de datos y sociólogo experto. "
            f"Se ha realizado un análisis de sentimiento en redes sociales sobre el tema: '{topic}'.\n\n"
            f"DATOS CUANTITATIVOS:\n{json.dumps(stats, indent=2, ensure_ascii=False)}\n\n"
            "TAREA:\n"
            "Escribe un breve informe ejecutivo (Storytelling) de 3 párrafos que interprete estos resultados.\n"
            "1. Párrafo 1: Resumen Global. ¿Cuál es el sentir general? ¿Hay polarización?\n"
            "2. Párrafo 2: Análisis Comparativo por Red Social. ¿Se comporta distinto Twitter que Instagram? ¿Por qué crees?\n"
            "3. Párrafo 3: Insights Cualitativos. Basándote en los números, ¿qué conclusiones estratégicas sacas?\n\n"
            "Usa un tono profesional pero atrapante. No listes solo números, cuenta la historia detrás de ellos."
        )

        try:
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=600
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"No se pudo generar el storytelling: {str(e)}"

    # --- RUTER PRINCIPAL ---
    def analyze_row(self, row):
        # ... (código previo omitido para brevedad, no cambia lógica de limpieza) ...
        # Combinamos contenido de post y comentario si existe, asegurando string
        p_content = str(row.get('post_content', ''))
        c_content = str(row.get('comment_content', ''))
        
        # Si el contenido está vacío en las columnas estándar, buscar en 'content' (formato flat)
        if not p_content and not c_content:
             content = str(row.get('content', ''))
        else:
             content = f"Post: {p_content} | Comment: {c_content}"
             
        # Lógica especial para LinkedIn (filas desplazadas) que queríamos conservar
        if len(content) < 5 or "nan" in content.lower():
            parts = []
            for val in row.values:
                s_val = str(val).strip()
                if s_val and s_val.lower() not in ['nan', 'none', '', 'linkedin', 'post', 'comment', 'objetivo']:
                    parts.append(s_val)
            if parts:
                content = " | ".join(parts)
        
        # Limitar longitud para ahorrar tokens y evitar errores
        content = content[:1000] 

        # AHORA SIEMPRE USAMOS DEEPSEEK
        return self.analyze_with_deepseek(content)

def process_dataframe_concurrently(df):
    processor = LLMProcessor()
    
    # Lista de resultados
    sentiments = []
    explanations = []
    tokens_usage = []
    
    print(f"Iniciando análisis CONCURRENTE de {len(df)} registros con DEEPSEEK EXCLUSIVAMENTE...")
    
    # Convertimos a lista de diccionarios para iterar
    rows = [row for _, row in df.iterrows()]
    
    results = []
    # ThreadPool para hacer peticiones HTTP concurrentes
    # DeepSeek NO tiene Rate Limit estricto. Subimos workers para mayor velocidad.
    with ThreadPoolExecutor(max_workers=60) as executor:
        # Usamos tqdm para barra de progreso sobre el iterador de resultados
        for res in tqdm(executor.map(processor.analyze_row, rows), total=len(rows), unit="posts"):
            results.append(res)
    
    # Desempaquetar
    for res in results:
        sentiments.append(res.get('sentiment', 'Error'))
        explanations.append(res.get('explanation', ''))
        tokens_usage.append(res.get('tokens', 0))
        
    df['sentiment_llm'] = sentiments
    df['explanation_llm'] = explanations
    df['tokens_llm'] = tokens_usage
    
    total_tokens = sum(tokens_usage)
    print(f"\n[Resumen] Total Tokens consumidos: {total_tokens}")
    print(f"         Promedio por post: {total_tokens/len(df):.1f}")
    
    return df

if __name__ == "__main__":
    # Bloque de prueba para ejecutar directamente
    # Intenta buscar un csv reciente en 'data' si existe, para prueba rápida
    target = "data/corpus_Venezuela.csv" # Default
    
    if os.path.exists(target):
        print(f"Probando con {target}...")
        try:
            df = pd.read_csv(target, sep=',', on_bad_lines='skip', encoding='utf-8')
            # Si falló la carga (columna única), reintentar punto y coma
            if len(df.columns) < 2:
                 df = pd.read_csv(target, sep=';', on_bad_lines='skip', encoding='utf-8')

            df_sample = df.head(3) # Prueba ultra rápida
            print("Procesando 3 filas de prueba...")
            res = process_dataframe_concurrently(df_sample)
            print(res[['sentiment_llm', 'explanation_llm']])
        except Exception as e:
            print(e)
