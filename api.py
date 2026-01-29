from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os
import uvicorn
from main_parallel import run_pipeline

app = FastAPI(title="Scraping & Analysis API")

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
        "message": f"El proceso para '{req.topic}' ha comenzado en segundo plano.",
        "expected_csv": f"data/corpus_{req.topic}.csv"
    }

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

@app.get("/")
def root():
    return {"message": "API de Web Scraping activa. POST a /scrape para usar."}

if __name__ == "__main__":
    # Ejecutar servidor en puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
