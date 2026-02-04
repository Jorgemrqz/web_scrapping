# Arquitectura de la Solución: Analizador de Sentimiento Multi-Plataforma

Este documento describe la arquitectura técnica de la solución implementada para el análisis de sentimiento en redes sociales, justificando las decisiones de diseño y tecnologías seleccionadas conforme a los requerimientos del proyecto.

## 1. Diseño General

La aplicación sigue una arquitectura **Cliente-Servidor (N-Capas)** desacoplada, permitiendo independencia entre la interfaz de usuario y la lógica de procesamiento intensivo.

*   **Frontend**: Single Page Application (SPA) construida con **Vue.js 3**.
*   **Backend**: API RESTful construida con **FastAPI (Python)**.
*   **Pipeline de Datos**: Sistema ETL (Extract, Transform, Load) concurrente integrado en el backend.

## 2. Tecnologías y Justificación

### A. Base de Datos: NoSQL [MongoDB]

Se seleccionó **MongoDB** (base de datos orientada a documentos) en lugar de una base de datos relacional (SQL) por las siguientes razones:

1.  **Flexibilidad de Esquema (Schema-less):** Las redes sociales (Twitter, Facebook, Instagram, LinkedIn) tienen estructuras de datos muy heterogéneas. Un post de Instagram tiene metadatos diferentes a un tweet. MongoDB permite almacenar estos objetos JSON tal cual llegan sin forzar normalizaciones complejas.
2.  **Jerarquía de Datos:** La relación *Post -> Comentarios -> Respuestas* se modela naturalmente como documentos anidados (embedded documents), lo que simplifica la lectura y escritura en una sola operación atómica, optimizando el rendimiento de lectura para el dashboard.
3.  **Escalabilidad:** Ideal para grandes volúmenes de datos no estructurados generados por scraping masivo.

### B. Procesamiento Paralelo y Concurrente

Dada la naturaleza intensiva de las tareas, se implementó un enfoque híbrido de paralelismo:

1.  **Multiprocessing (Para Scraping):**
    *   **Implementación:** Librería `multiprocessing` de Python.
    *   **Justificación:** El scraping con navegadores (Playwright) consume mucha CPU y memoria. Usar *Subprocesos* (Procesos independientes) evita el bloqueo por el GIL (Global Interpreter Lock) de Python, permitiendo que 4 navegadores operen en núcleos de CPU distintos simultáneamente sin ralentizarse entre sí.
2.  **Multithreading (Para LLMs):**
    *   **Implementación:** `ThreadPoolExecutor` con 60 workers.
    *   **Justificación:** Las llamadas a la API del LLM son operaciones ligadas a I/O (I/O bound). Mientras el programa espera la respuesta del servidor de IA, la CPU está ociosa. El uso de threads permite lanzar decenas de peticiones simultáneas, reduciendo el tiempo de clasificación de 5 minutos a segundos.

### C. Servicios de Lenguaje (LLM) e Inteligencia Artificial

Se utiliza **DeepSeek V3** (vía API compatible con OpenAI) para el procesamiento de lenguaje natural.

*   **Clasificación de Sentimiento:** Analiza el texto de posts y comentarios para determinar la polaridad (Positivo, Neutro, Negativo) con comprensión de sarcasmo y contexto local.
*   **Storytelling (Generación de Texto):** El LLM actúa como un analista experto que interpreta las estadísticas agregadas y redacta un informe ejecutivo en lenguaje natural, cumpliendo el requerimiento de "dar sentido a los resultados".
*   **Justificación:** Los modelos LLM modernos superan a las librerías tradicionales (como NLTK o Vader) en la detección de matices complejos y en la capacidad de generar resúmenes coherentes (Storytelling).

## 3. Flujo de Datos

1.  **Input:** Usuario solicita un tema en el Frontend.
2.  **Orquestación:** API recibe solicitud y lanza 4 procesos `worker` en paralelo.
3.  **Extracción:** Cada worker lanza una instancia de navegador controlado (Playwright) para extraer datos de su red social asignada.
4.  **Transformación (Fase LLM):** Los datos crudos pasan por el `LLMProcessor`, que utiliza concurrencia masiva para clasificar el sentimiento de cada texto.
5.  **Persistencia:** Los resultados estructurados se guardan en **MongoDB**.
6.  **Análisis:** Se genera un reporte narrativo (storytelling) y estadísticas agregadas.
7.  **Visualización:** El Frontend consulta la API y renderiza gráficos interactivos (Chart.js) y tablas dinámicas.
