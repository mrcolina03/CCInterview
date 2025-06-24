from typing import Dict
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.datastructures import FormData
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db.mongo import db
from auth.dependencies import get_current_user
import os

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/config"))

@router.get("/admin", response_class=HTMLResponse)
async def index_config(request: Request, user: dict = Depends(get_current_user)):
    if user.get("rol") != "admin":
        return RedirectResponse("/", status_code=303)
    msg = request.query_params.get("msg")  # Leer parámetro msg
    return templates.TemplateResponse("admin.html", {"request": request, "user": user, "msg": msg})


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
    return RedirectResponse("/config/admin?msg=ok", status_code=303)

@router.get("/criterios", response_class=HTMLResponse)
async def mostrar_criterios(request: Request, user: dict = Depends(get_current_user)):
    if user.get("rol") != "admin":
        return RedirectResponse("/", status_code=303)

    criterios = await db["config"].find_one({"_id": "criterios_adaptacion"})
    if not criterios:
        criterios = {
            "_id": "criterios_adaptacion",
            "subtematicas": {
                "umbral_dominio": {"valor": 10, "porcentaje": 1, "activo": True},
                "num_preguntas": {"valor": 10, "porcentaje": 1, "activo": True},
                "refuerzo_repeticion": {"porcentaje": 0.3, "activo": True}
            },
            "habilidades": {
                "umbral_dominio_global": {"valor": 10, "porcentaje": 1, "activo": True},
                "num_subtematicas": {"valor": 10, "porcentaje": 1, "activo": True}
            }
        }
        await db["config"].insert_one(criterios)

    return templates.TemplateResponse("criterios_adaptacion.html", {"request": request, "user": user, "criterios": criterios})

@router.post("/criterios")
async def guardar_criterios(
    request: Request,
    user: dict = Depends(get_current_user),
    # Subtemáticas
    umbral_dominio_valor: int = Form(...),
    umbral_dominio_porcentaje: float = Form(...),
    umbral_dominio_activo: bool = Form(...),
    num_preguntas_valor: int = Form(...),
    num_preguntas_porcentaje: float = Form(...),
    num_preguntas_activo: bool = Form(...),
    refuerzo_repeticion_porcentaje: float = Form(...),
    refuerzo_repeticion_activo: bool = Form(...),
    # Habilidades
    umbral_global_valor: int = Form(...),
    umbral_global_porcentaje: float = Form(...),
    umbral_global_activo: bool = Form(...),
    num_subtematicas_valor: int = Form(...),
    num_subtematicas_porcentaje: float = Form(...),
    num_subtematicas_activo: bool = Form(...)
):
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Acceso no autorizado")

    criterios = {
        "_id": "criterios_adaptacion",
        "subtematicas": {
            "umbral_dominio": {
                "valor": umbral_dominio_valor,
                "porcentaje": umbral_dominio_porcentaje,
                "activo": umbral_dominio_activo
            },
            "num_preguntas": {
                "valor": num_preguntas_valor,
                "porcentaje": num_preguntas_porcentaje,
                "activo": num_preguntas_activo
            },
            "refuerzo_repeticion": {
                "porcentaje": refuerzo_repeticion_porcentaje,
                "activo": refuerzo_repeticion_activo
            }
        },
        "habilidades": {
            "umbral_dominio_global": {
                "valor": umbral_global_valor,
                "porcentaje": umbral_global_porcentaje,
                "activo": umbral_global_activo
            },
            "num_subtematicas": {
                "valor": num_subtematicas_valor,
                "porcentaje": num_subtematicas_porcentaje,
                "activo": num_subtematicas_activo
            }
        }
    }

    await db["config"].replace_one({"_id": "criterios_adaptacion"}, criterios, upsert=True)
    return RedirectResponse("/config/admin?msg=ok", status_code=303)

@router.get("/plantillas", response_class=HTMLResponse)
async def mostrar_plantillas(request: Request, user: dict = Depends(get_current_user)):
    if user.get("rol") != "admin":
        return RedirectResponse("/", status_code=303)

    config = await db["config"].find_one({"_id": "plantillas_codigo"})
    if not config:
        config = {
            "_id": "plantillas_codigo",
            "plantillas": {
                "python": "# Código Python aquí",
                "javascript": "// Código JavaScript aquí",
                "php": "<?php\n\n// Código PHP aquí\n\n?>"
            }
        }
        await db["config"].insert_one(config)

    return templates.TemplateResponse("plantillas_judge.html", {
        "request": request,
        "user": user,
        "plantillas": config["plantillas"]
    })


@router.post("/plantillas")
async def guardar_plantillas(request: Request, user: dict = Depends(get_current_user)):
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Acceso no autorizado")

    form: FormData = await request.form()
    plantillas: Dict[str, str] = {}

    for key, value in form.multi_items():
        if key.startswith("plantilla_"):
            lenguaje = key.replace("plantilla_", "")
            plantillas[lenguaje] = value

    await db["config"].replace_one(
        {"_id": "plantillas_codigo"},
        {"_id": "plantillas_codigo", "plantillas": plantillas},
        upsert=True
    )

    return RedirectResponse("/config/admin?msg=ok", status_code=303)
