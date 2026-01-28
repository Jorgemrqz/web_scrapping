import os
import json
import time
import requests
import google.generativeai as genai
from openai import OpenAI
from groq import Groq
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Importar claves desde config (Las añadiremos luego)
try:
    from config import OPENAI_API_KEY, GEMINI_API_KEY, GROK_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY
except ImportError:
    OPENAI_API_KEY = ""
    GEMINI_API_KEY = ""
    GROK_API_KEY = ""
    DEEPSEEK_API_KEY = ""
    GROQ_API_KEY = ""

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

    # --- 1. FACEBOOK -> OPENAI ---
    def analyze_with_openai(self, text):
        if not OPENAI_API_KEY: return {"sentiment": "N/A", "explanation": "Falta OPENAI_API_KEY"}
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Texto: {text}"}
                ],
                temperature=0
            )
            return self._safe_json_parse(response.choices[0].message.content)
        except Exception as e:
            return {"sentiment": "Error", "explanation": str(e)}

    # --- 2. INSTAGRAM -> GEMINI ---
    def analyze_with_gemini(self, text):
        if not GEMINI_API_KEY: return {"sentiment": "N/A", "explanation": "Falta GEMINI_API_KEY"}
        try:
            # Uso directo de API REST para evitar conflictos de librería obsoleta
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{
                    "parts": [{"text": f"{self.system_prompt}\n\nTexto a analizar: {text}"}]
                }]
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code != 200:
                return {"sentiment": "Error", "explanation": f"Gemini Error {response.status_code}: {response.text}"}
                
            result_json = response.json()
            # Extraer texto de la respuesta
            try:
                candidate_text = result_json['candidates'][0]['content']['parts'][0]['text']
                return self._safe_json_parse(candidate_text)
            except (KeyError, IndexError) as e:
                 return {"sentiment": "Error", "explanation": f"Estructura inesperada de Gemini: {str(e)}"}

        except Exception as e:
            return {"sentiment": "Error", "explanation": str(e)}

    # --- 3. X (TWITTER) -> GROK (xAI) ---
    def analyze_with_grok(self, text):
        if not GROK_API_KEY: return {"sentiment": "N/A", "explanation": "Falta GROK_API_KEY"}
        try:
            # xAI (Grok) es compatible con el SDK de OpenAI
            # Usamos la URL de INFERENCIA
            client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
            
            response = client.chat.completions.create(
                model="grok-4-latest", # Modelo actualizado por el usuario
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0
            )
            return self._safe_json_parse(response.choices[0].message.content)
        except Exception as e:
            return {"sentiment": "Error", "explanation": f"Grok Error: {str(e)}"}

    # --- 4. LINKEDIN -> DEEPSEEK ---
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
                temperature=0
            )
            return self._safe_json_parse(response.choices[0].message.content)
        except Exception as e:
            return {"sentiment": "Error", "explanation": str(e)}

    # --- 5. INSTAGRAM -> LLAMA 3 (Groq) ---
    def analyze_with_llama(self, text):
        if not GROQ_API_KEY: return {"sentiment": "N/A", "explanation": "Falta GROQ_API_KEY"}
        try:
            client = Groq(api_key=GROQ_API_KEY)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile", # Modelo muy potente y rápido
                messages=[
                    {"role": "system", "content": self.system_prompt + "\n\nIMPORTANTE: Responde ÚNICAMENTE con el objeto JSON válido. No incluyas bloques de código markdown ```json ... ```, solo el JSON puro."},
                    {"role": "user", "content": text}
                ],
                temperature=0,
                response_format={"type": "json_object"} # Forzar JSON puro
            )
            return self._safe_json_parse(completion.choices[0].message.content)
        except Exception as e:
            return {"sentiment": "Error", "explanation": f"Llama Error: {str(e)}"}

    # --- 5. INSTAGRAM -> LLAMA 3 (Groq) ---
    def analyze_with_llama(self, text):
        if not GROQ_API_KEY: return {"sentiment": "N/A", "explanation": "Falta GROQ_API_KEY"}
        try:
            client = Groq(api_key=GROQ_API_KEY)
            completion = client.chat.completions.create(
                model="llama3-8b-8192", # Modelo 8B: Más rápido y con cuota separada
                messages=[
                    {"role": "system", "content": self.system_prompt + "\n\nIMPORTANTE: Responde ÚNICAMENTE con el objeto JSON válido. No incluyas bloques de código markdown ```json ... ```, solo el JSON puro."},
                    {"role": "user", "content": text}
                ],
                temperature=0,
                response_format={"type": "json_object"} # Forzar JSON puro
            )
            return self._safe_json_parse(completion.choices[0].message.content)
        except Exception as e:
            return {"sentiment": "Error", "explanation": f"Llama Error: {str(e)}"}

    # --- RUTER PRINCIPAL ---
    def analyze_row(self, row):
        # Convertir a string para evitar error con NaN (float)
        platform = str(row.get('platform', '')).lower()
        source = str(row.get('source', '')).lower()
        
        # Combinamos contenido de post y comentario si existe, asegurando string
        p_content = str(row.get('post_content', ''))
        c_content = str(row.get('comment_content', ''))
        
        # Si el contenido está vacío en las columnas estándar, buscar en 'content' (formato flat)
        if not p_content and not c_content:
             content = str(row.get('content', ''))
        else:
             content = f"Post: {p_content} | Comment: {c_content}"
        
        # Limitar longitud
        content = content[:500] 

        # Lógica de detección reforzada
        is_fb = 'facebook' in platform or 'facebook' in source
        is_ig = 'instagram' in platform or 'instagram' in source
        is_x = 'x' in platform or 'twitter' in platform or 'twitter' in source
        is_li = 'linkedin' in platform or 'linkedin' in source

        if is_fb:
            return self.analyze_with_openai(content)
        elif is_ig:
            # CAMBIO: Usamos Llama 3 en lugar de Gemini
            return self.analyze_with_llama(content)
        elif is_x:
            return self.analyze_with_grok(content)
        elif is_li:
            # Fallback inteligente para LinkedIn (filas desplazadas)
            if len(content) < 5 or "nan" in content.lower():
                # Unir todo lo que no sea nulo ni palabras clave de estructura
                parts = []
                for val in row.values:
                    s_val = str(val).strip()
                    if s_val and s_val.lower() not in ['nan', 'none', '', 'linkedin', 'post', 'comment', 'objetivo']:
                        parts.append(s_val)
                # Si recuperamos algo, lo usamos
                if parts:
                    content = " | ".join(parts)
            
            return self.analyze_with_deepseek(content)
        else:
            return {"sentiment": "N/A", "explanation": f"Plataforma desconocida: {platform}/{source}"}

from tqdm import tqdm

def process_dataframe_concurrently(df):
    processor = LLMProcessor()
    
    # Lista de resultados
    sentiments = []
    explanations = []
    
    print(f"Iniciando análisis CONCURRENTE de {len(df)} registros con 4 LLMs...")
    
    # Convertimos a lista de diccionarios para iterar
    rows = [row for _, row in df.iterrows()]
    
    results = []
    # ThreadPool para hacer peticiones HTTP concurrentes
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Usamos tqdm para barra de progreso sobre el iterador de resultados
        for res in tqdm(executor.map(processor.analyze_row, rows), total=len(rows), unit="posts"):
            results.append(res)
    
    # Desempaquetar
    for res in results:
        sentiments.append(res.get('sentiment', 'Error'))
        explanations.append(res.get('explanation', ''))
        
    df['sentiment_llm'] = sentiments
    df['explanation_llm'] = explanations
    return df
