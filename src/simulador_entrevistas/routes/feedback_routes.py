from utils.codigo import evaluar_respuesta_codigo, orquestar_pregunta_codigo
from bson import ObjectId
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, Path
from db.mongo import db
import os

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/feedback"))

@router.get("/resultados/{entrevista_id}", response_class=HTMLResponse)
async def mostrar_resultados(request: Request, entrevista_id: str = Path(...)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")

    from auth.auth import decode_token
    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/auth/login")

    entrevista = await db["entrevistas"].find_one({"_id": ObjectId(entrevista_id)})
    if not entrevista:
        return RedirectResponse(url="/")

    preguntas = await db["preguntas"].find({
        "entrevista_id": ObjectId(entrevista_id),
        "tipo": "codigo"
    }).to_list(length=None)

    pregunta_ids = [p["_id"] for p in preguntas]
    respuestas = await db["respuestas"].find({
        "pregunta_id": {"$in": pregunta_ids}
    }).to_list(length=None)

    for respuesta in respuestas:
        if "lenguaje" in respuesta and "salida" not in respuesta:
            try:
                print(f"Compilando código: {respuesta['_id']}")
                await evaluar_respuesta_codigo(db, str(respuesta["_id"]))
            except Exception as e:
                print(f"Error compilando respuesta {respuesta['_id']}: {e}")

        if "lenguaje" in respuesta and "feedback" not in respuesta:
            try:
                print(f"Evaluando con LLM: {respuesta['_id']}")
                await orquestar_pregunta_codigo(db, str(respuesta["_id"]))
            except Exception as e:
                print(f"Error generando feedback con LLM: {e}")
                
    print(f"respuestas: {respuestas}")
    
    respuestas = await db["respuestas"].find({
        "pregunta_id": {"$in": pregunta_ids}
    }).to_list(length=None)

    return templates.TemplateResponse("resultados.html", {
        "request": request,
        "usuario": payload,
        "entrevista": entrevista,
        "preguntas": preguntas,
        "respuestas": respuestas
    })
