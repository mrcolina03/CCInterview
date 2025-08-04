import httpx
import os
import random

JUDGE0_API_URL = "https://judge0-ce.p.rapidapi.com"
HEADERS = {
    "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
    "X-RapidAPI-Key": os.getenv("JUDGE0_API_KEY"), 
    "Content-Type": "application/json"
}

RAPIDDAPI_KEYS = [
    os.getenv("RAPIDAPI_KEY_1"),
    os.getenv("RAPIDAPI_KEY_2"),
    os.getenv("RAPIDAPI_KEY_3"),
    os.getenv("RAPIDAPI_KEY_4"),
]

# Obtener todos los lenguajes disponibles
async def obtener_lenguajes_judge0():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{RAPIDDAPI_KEYS[0]}/languages", headers=HEADERS)
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
        api_key = RAPIDDAPI_KEYS[random.randint(0, len(RAPIDDAPI_KEYS) - 1)]
        response = await client.post(f"{api_key}/submissions?wait=true", headers=HEADERS, json=payload)
        print("API KEY USADA:", api_key)
        response.raise_for_status()
        return response.json()
