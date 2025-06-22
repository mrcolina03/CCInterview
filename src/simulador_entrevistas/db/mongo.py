from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("La variable de entorno MONGO_URI no está definida")

client = AsyncIOMotorClient(MONGO_URI)
db = client["ccinterview"]


