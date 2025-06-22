from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db.mongo import db
from auth.dependencies import get_current_user
import os

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/config"))

@router.get("/duracion", response_class=HTMLResponse)
async def mostrar_configuracion(request: Request, user: dict = Depends(get_current_user)):
    if user.get("rol") != "admin":
        return RedirectResponse("/", status_code=303)

    config = await db["config"].find_one({"_id": "duraciones"})
    if not config:
        config = {
            "_id": "duraciones",
            "corta": {"minutos": 20, "preguntas": 10, "tecnicas": 4, "blandas": 3, "codigo": 3},
            "mediana": {"minutos": 40, "preguntas": 20, "tecnicas": 8, "blandas": 6, "codigo": 6},
            "larga": {"minutos": 60, "preguntas": 30, "tecnicas": 10, "blandas": 10, "codigo": 10},
        }
        await db["config"].insert_one(config)

    return templates.TemplateResponse("duracion.html", {"request": request, "user": user, "config": config})


@router.post("/duracion")
async def guardar_configuracion(
    request: Request,
    user: dict = Depends(get_current_user),
    corta_minutos: int = Form(...), corta_preguntas: int = Form(...),
    corta_tecnicas: int = Form(...), corta_blandas: int = Form(...), corta_codigo: int = Form(...),
    mediana_minutos: int = Form(...), mediana_preguntas: int = Form(...),
    mediana_tecnicas: int = Form(...), mediana_blandas: int = Form(...), mediana_codigo: int = Form(...),
    larga_minutos: int = Form(...), larga_preguntas: int = Form(...),
    larga_tecnicas: int = Form(...), larga_blandas: int = Form(...), larga_codigo: int = Form(...)
):
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Acceso no autorizado")

    # Validaciones de consistencia
    def validar_suma(nombre, total, tecnicas, blandas, codigo):
        suma = tecnicas + blandas + codigo
        if suma != total:
            raise HTTPException(
                status_code=400,
                detail=f"La suma de preguntas de {nombre} ({suma}) no coincide con el total ({total})"
            )

    validar_suma("CORTA", corta_preguntas, corta_tecnicas, corta_blandas, corta_codigo)
    validar_suma("MEDIANA", mediana_preguntas, mediana_tecnicas, mediana_blandas, mediana_codigo)
    validar_suma("LARGA", larga_preguntas, larga_tecnicas, larga_blandas, larga_codigo)

    nueva_config = {
        "_id": "duraciones",
        "corta": {
            "minutos": corta_minutos, "preguntas": corta_preguntas,
            "tecnicas": corta_tecnicas, "blandas": corta_blandas, "codigo": corta_codigo
        },
        "mediana": {
            "minutos": mediana_minutos, "preguntas": mediana_preguntas,
            "tecnicas": mediana_tecnicas, "blandas": mediana_blandas, "codigo": mediana_codigo
        },
        "larga": {
            "minutos": larga_minutos, "preguntas": larga_preguntas,
            "tecnicas": larga_tecnicas, "blandas": larga_blandas, "codigo": larga_codigo
        },
    }

    await db["config"].replace_one({"_id": "duraciones"}, nueva_config, upsert=True)
    return RedirectResponse("/", status_code=303)
