import os
import json
import time
import requests
import google.generativeai as genai
from openai import OpenAI
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Importar claves desde config (Las añadiremos luego)
try:
    from config import OPENAI_API_KEY, GEMINI_API_KEY, GROK_API_KEY, DEEPSEEK_API_KEY
except ImportError:
    OPENAI_API_KEY = ""
    GEMINI_API_KEY = ""
    GROK_API_KEY = ""
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
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            # Gemini a veces es verboso, forzamos JSON
            prompt = f"{self.system_prompt}\n\nTexto a analizar: {text}"
            response = model.generate_content(prompt)
            return self._safe_json_parse(response.text)
        except Exception as e:
            return {"sentiment": "Error", "explanation": str(e)}

    # --- 3. X (TWITTER) -> GROK (xAI) ---
    def analyze_with_grok(self, text):
        if not GROK_API_KEY: return {"sentiment": "N/A", "explanation": "Falta GROK_API_KEY"}
        try:
            # xAI (Grok) es compatible con el SDK de OpenAI
            # Usamos la URL de INFERENCIA, no la de Management
            client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
            
            response = client.chat.completions.create(
                model="grok-beta", # Modelo estándar de inferencia
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
            # DeepSeek es compatible con OpenAI Client cambiando la Base URL
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Texto: {text}"}
                ],
                temperature=0
            )
            return self._safe_json_parse(response.choices[0].message.content)
        except Exception as e:
            return {"sentiment": "Error", "explanation": str(e)}

    # --- RUTER PRINCIPAL ---
    def analyze_row(self, row):
        platform = row.get('platform', '').lower()
        # Combinamos contenido de post y comentario si existe
        content = f"Post: {row.get('post_content', '')} | Comment: {row.get('comment_content', '')}"
        
        # Limitar longitud para no gastar tokens excesivos en pruebas
        content = content[:500] 

        if 'facebook' in platform:
            return self.analyze_with_openai(content)
        elif 'instagram' in platform:
            return self.analyze_with_gemini(content)
        elif 'x' in platform or 'twitter' in platform:
            return self.analyze_with_grok(content)
        elif 'linkedin' in platform:
            return self.analyze_with_deepseek(content)
        else:
            return {"sentiment": "N/A", "explanation": "Plataforma desconocida"}

def process_dataframe_concurrently(df):
    processor = LLMProcessor()
    
    # Lista de resultados
    sentiments = []
    explanations = []
    
    print("Iniciando análisis de sentimientos concurrente con 4 LLMs...")
    
    # ThreadPool para hacer peticiones HTTP concurrentes
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Mapeamos la función a cada fila
        results = list(executor.map(processor.analyze_row, [row for _, row in df.iterrows()]))
    
    # Desempaquetar
    for res in results:
        sentiments.append(res.get('sentiment', 'Error'))
        explanations.append(res.get('explanation', ''))
        
    df['sentiment_llm'] = sentiments
    df['explanation_llm'] = explanations
    return df
