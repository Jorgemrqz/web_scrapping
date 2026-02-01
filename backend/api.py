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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
