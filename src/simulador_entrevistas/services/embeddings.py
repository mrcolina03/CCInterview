import logging
from openai import AsyncOpenAI
import numpy as np
import os

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def vectorizar_texto(texto: str):
    try:
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=texto
        )
        return response.data[0].embedding
    except Exception as e:
        logging.error(f"Error al generar embedding: {e}")
        return None

def similitud_coseno(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
