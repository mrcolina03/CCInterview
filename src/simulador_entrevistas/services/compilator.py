import httpx
import os

JUDGE0_API_URL = "https://judge0-ce.p.rapidapi.com"
HEADERS = {
    "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
    "X-RapidAPI-Key": os.getenv("JUDGE0_API_KEY"), 
    "Content-Type": "application/json"
}

# Obtener todos los lenguajes disponibles
async def obtener_lenguajes_judge0():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{JUDGE0_API_URL}/languages", headers=HEADERS)
        response.raise_for_status()
        return response.json()

# Enviar código para compilación
async def ejecutar_codigo_judge0(source_code: str, language_id: int, stdin: str = ""):
    payload = {
        "source_code": source_code,
        "language_id": language_id,
        "stdin": stdin
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{JUDGE0_API_URL}/submissions?wait=true", headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json()
