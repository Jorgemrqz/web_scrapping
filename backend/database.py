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

    def save_analysis(self, topic, analysis_data):
        """Guarda el resultado del análisis (stats, charts, storytelling) en una colección separada"""
        if not self.is_connected: return False
        try:
            analysis_coll = self.db["analysis_results"]
            doc = {
                "topic": topic,
                "data": analysis_data,
                "updated_at": datetime.now()
            }
            # Upsert
            analysis_coll.update_one(
                {"topic": topic},
                {"$set": doc},
                upsert=True
            )
            print(f"[MongoDB] Análisis guardado para '{topic}'")
            return True
        except Exception as e:
            print(f"[MongoDB] Error guardando análisis: {e}")
            return False

    def get_analysis(self, topic):
        """Recupera el análisis más reciente para un tema"""
        if not self.is_connected: return None
        try:
            analysis_coll = self.db["analysis_results"]
            # Buscar coincidencia exacta o case-insensitive
            res = analysis_coll.find_one({"topic": topic})
            if not res:
                # Try regex for case insensitive
                res = analysis_coll.find_one({"topic": {"$regex": f"^{topic}$", "$options": "i"}})
            
            if res:
                return res["data"]
            return None
        except Exception as e:
            print(f"[MongoDB] Error recuperando análisis: {e}")
            return None

    def get_analysis_history(self):
        """Devuelve una lista de temas analizados y su fecha de actualización"""
        if not self.is_connected: return []
        try:
            analysis_coll = self.db["analysis_results"]
            # Proyección para traer solo topic y updated_at, y stats para el count
            cursor = analysis_coll.find({}, {
                "topic": 1, 
                "updated_at": 1, 
                "data.stats.global_counts": 1, 
                "_id": 0
            }).sort("updated_at", -1)
            
            history = []
            for doc in cursor:
                total_comments = 0
                if "data" in doc and "stats" in doc["data"] and "global_counts" in doc["data"]["stats"]:
                    counts = doc["data"]["stats"]["global_counts"]
                    total_comments = sum(counts.values()) if counts else 0
                
                history.append({
                    "topic": doc["topic"],
                    "updated_at": doc.get("updated_at"),
                    "total_comments": total_comments
                })
            return history
        except Exception as e:
            print(f"[MongoDB] Error recuperando historial: {e}")
            return []

    def delete_analysis_history(self, topic):
        """Elimina el análisis y los posts asociados a un tema"""
        if not self.is_connected: return False
        try:
            # Eliminar análisis
            analysis_coll = self.db["analysis_results"]
            res1 = analysis_coll.delete_one({"topic": topic})
            
            # Eliminar posts (Opcional, pero para limpieza completa)
            res2 = self.collection.delete_many({"topic": topic})
            
            # Si se borró algo, retornamos True
            if res1.deleted_count > 0:
                print(f"[MongoDB] Historial eliminado para '{topic}'")
                return True
            return False
        except Exception as e:
            print(f"[MongoDB] Error eliminando historial: {e}")
            return False

    def init_job_status(self, topic, platforms, limit):
        """Inicializa el estado de un trabajo de scraping"""
        if not self.is_connected: return
        try:
            status_coll = self.db["job_status"]
            stages = {}
            for p in platforms:
                stages[p] = {"current": 0, "total": limit, "status": "pending"}
            
            doc = {
                "topic": topic,
                "stages": stages,
                "llm_status": "pending", # pending, running, completed
                "updated_at": datetime.now()
            }
            status_coll.update_one({"topic": topic}, {"$set": doc}, upsert=True)
        except Exception as e:
            print(f"[MongoDB] Error inicilizando status: {e}")

    def update_stage_progress(self, topic, platform, current, status="running"):
        """Actualiza el progreso de una plataforma específica"""
        if not self.is_connected: return
        try:
            status_coll = self.db["job_status"]
            update_field = f"stages.{platform}"
            status_coll.update_one(
                {"topic": topic},
                {"$set": {
                    f"{update_field}.current": current,
                    f"{update_field}.status": status,
                    "updated_at": datetime.now()
                }}
            )
        except Exception as e:
            print(f"[MongoDB] Error actualizando progreso {platform}: {e}")

    def update_llm_status(self, topic, status):
        """Actualiza el estado del LLM"""
        if not self.is_connected: return
        try:
            status_coll = self.db["job_status"]
            status_coll.update_one(
                {"topic": topic},
                {"$set": {"llm_status": status, "updated_at": datetime.now()}}
            )
        except Exception as e:
            print(f"[MongoDB] Error actualizando LLM status: {e}")

    def get_job_status(self, topic):
        """Obtiene el estado actual del job"""
        if not self.is_connected: return None
        try:
            status_coll = self.db["job_status"]
            return status_coll.find_one({"topic": topic}, {"_id": 0})
        except Exception as e:
             return None
