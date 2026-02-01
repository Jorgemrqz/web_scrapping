from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os
import json
import uvicorn
from main_parallel import run_pipeline

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Scraping & Analysis API")

# Configurar CORS para permitir peticiones desde el frontend (Vue)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir todo para evitar problemas en desarrollo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "SentimentPulse API Running"}

class ScrapeRequest(BaseModel):
    topic: str
    limit: int = 10

@app.post("/scrape")
async def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Inicia un proceso de scraping en segundo plano.
    """
    if not req.topic:
        raise HTTPException(status_code=400, detail="El campo 'topic' es obligatorio.")
        
    print(f"[API] Recibida petición para tema: {req.topic}")
    
    # Ejecutamos en background para no bloquear la respuesta inmediata
    background_tasks.add_task(run_pipeline, req.topic, req.limit)
    
    return {
        "status": "processing", 
        "message": f"Análisis de '{req.topic}' iniciado.",
        "topic": req.topic
    }

@app.get("/results/{topic}")
def get_results(topic: str):
    """Devuelve el JSON de análisis si existe (desde MongoDB)."""
    try:
        from database import Database
        db = Database()
        if db.is_connected:
            data = db.get_analysis(topic)
            if data:
                return data
            else:
                 # Check if job is still processing?
                 # For now, 404
                 pass
        else:
            print("[API] MongoDB no conectado")
    except Exception as e:
        print(f"[API Error] {e}")

    # Fallback legacy or 404
    raise HTTPException(status_code=404, detail="Analysis not ready or not found in DB")

@app.get("/history")
def get_history():
    """Devuelve el historial de búsquedas."""
    try:
        from database import Database
        db = Database()
        if db.is_connected:
            return db.get_analysis_history()
        return []
    except Exception as e:
        print(f"[API Error] {e}")
        return []

@app.delete("/history/{topic}")
def delete_history_item(topic: str):
    """Elimina un item del historial."""
    try:
        from database import Database
        db = Database()
        if db.is_connected:
            success = db.delete_analysis_history(topic)
            if success:
                return {"status": "deleted", "topic": topic}
            else:
                 raise HTTPException(status_code=404, detail="Topic not found or error deleting")
        else:
            raise HTTPException(status_code=500, detail="Database connection error")
    except Exception as e:
        print(f"[API Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-data")
def list_data():
    """Lista los archivos CSV generados en la carpeta data"""
    try:
        if not os.path.exists("data"):
            return {"files": []}
        files = [f for f in os.listdir("data") if f.endswith(".csv")]
        return {"files": files}
    except Exception as e:
        return {"error": str(e)}

# Servir Frontend (Archivos estáticos)
# Esto DEBE ir al final para no bloquear otras rutas
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    # Ejecutar servidor en puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
