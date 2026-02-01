import os
from pymongo import MongoClient
from datetime import datetime

class Database:
    def __init__(self, uri="mongodb://localhost:27017/", db_name="social_sentiment_db"):
        """
        Inicializa la conexión a MongoDB.
        Por defecto intenta conectar a localhost.
        Para usar Atlas, cambia la URI.
        """
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Comprobar conexión
            self.client.server_info()
            self.db = self.client[db_name]
            self.collection = self.db["posts"]
            self.is_connected = True
            print(f"[MongoDB] Conectado exitosamente a {db_name}")
        except Exception as e:
            print(f"[MongoDB] Error de conexión: {e}")
            self.is_connected = False

    def save_corpus(self, topic, data):
        """
        Guarda una lista de posts estructurados (con comentarios) en MongoDB.
        Evita duplicados basándose en una clave única (plataforma + contenido/id).
        """
        if not self.is_connected:
            print("[MongoDB] No hay conexión, omitiendo guardado.")
            return 0

        if not data:
            return 0
        
        scrape_date = datetime.now()
        count = 0
        
        for item in data:
            # Crear documento enriquecido
            doc = item.copy()
            doc["topic"] = topic
            doc["last_updated"] = scrape_date
            
            # Definir filtro único para evitar duplicados
            # Usamos platform + content (o url/id si tuviéramos) como "clave primaria" lógica
            # MongoDB creará un _id automático, pero usamos esto para update_one (upsert)
            
            # Intentamos usar 'post_index' si existe para unicidad, sino contenido
            filter_query = {
                "topic": topic,
                "platform": doc.get("platform"),
                "content": doc.get("content") 
            }
            
            try:
                # Upsert: Si existe actualiza, si no crea
                self.collection.update_one(
                    filter_query,
                    {"$set": doc},
                    upsert=True
                )
                count += 1
            except Exception as e:
                print(f"[MongoDB] Error guardando documento: {e}")

        print(f"[MongoDB] Procesados {count} documentos para el tema '{topic}'.")
        return count

    def get_historical_data(self, topic):
        """Recupera todos los posts de un tema"""
        if not self.is_connected: return []
        return list(self.collection.find({"topic": topic}, {"_id": 0}))
