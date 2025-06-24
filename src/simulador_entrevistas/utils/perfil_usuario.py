from services.llm import generar_perfil_usuario
from db.mongo import db
from bson import ObjectId

async def crear_perfil_usuario(cv_dict: dict):
    perfil = await generar_perfil_usuario(cv_dict)
    if perfil is None:
        raise ValueError("Error inesperado al generar el perfil del usuario")

    # Ya no insertamos el perfil aquí, solo lo retornamos
    return perfil

async def eliminar_perfil(user: dict):
    user_id = ObjectId(user["sub"])
    await db["perfil_usuario"].delete_one({"usuario_id": user_id})
    await db["curriculum"].delete_one({"usuario_id": user_id})
