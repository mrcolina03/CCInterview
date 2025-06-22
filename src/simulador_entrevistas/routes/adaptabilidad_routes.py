# routes/adaptabilidad_routes.py

from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from auth.auth import decode_token
from db.mongo import db
import os
from utils.adaptabilidad import (
    evaluar_creacion_nueva_habilidad,
    evaluar_creacion_nueva_subtematica,
    generar_nueva_habilidad,
    generar_nueva_subtematica,
    obtener_config,
    escoger_habilidades_subtematica,
    detectar_lenguajes_perfil

)

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/adaptabilidad"))

async def get_current_user_id(request: Request):
    token = request.cookies.get("access_token")
    if token:
        payload = decode_token(token)
        if payload:
            return payload.get("sub")
    return None

def formatear_criterios(config):
    criterios = {"habilidades": {}, "subtematicas": {}}
    for cat in ["habilidades", "subtematicas"]:
        for clave, val in config.get(cat, {}).items():
            criterios[cat][clave] = {
                "valor": val.get("valor"),
                "porcentaje": val.get("porcentaje"),
                "activo": val.get("activo")
            }
    return criterios

@router.get("/probar", response_class=HTMLResponse)
async def probar_creacion(request: Request, user_id: str = Depends(get_current_user_id)):
    if not user_id:
        return RedirectResponse(url="/auth/login")

    crear_tecnica = await evaluar_creacion_nueva_habilidad(db, user_id, "tecnica")
    crear_blanda = await evaluar_creacion_nueva_habilidad(db, user_id, "blanda")

    nuevas_subs_tecnicas = await evaluar_creacion_nueva_subtematica(db, user_id, "tecnica")
    nuevas_subs_blandas = await evaluar_creacion_nueva_subtematica(db, user_id, "blanda")

    # Generar lo necesario
    habilidad_tecnica_generada = await generar_nueva_habilidad(db, user_id, "tecnica") if crear_tecnica else None
    habilidad_blanda_generada = await generar_nueva_habilidad(db, user_id, "blanda") if crear_blanda else None

    subtematicas_generadas = {
        "tecnica": {},
        "blanda": {}
    }

    for habilidad, debe_crear in nuevas_subs_tecnicas.items():
        if debe_crear:
            nueva = await generar_nueva_subtematica(db, user_id, habilidad, "tecnica")
            if nueva:
                subtematicas_generadas["tecnica"][habilidad] = nueva["nombre"]

    for habilidad, debe_crear in nuevas_subs_blandas.items():
        if debe_crear:
            nueva = await generar_nueva_subtematica(db, user_id, habilidad, "blanda")
            if nueva:
                subtematicas_generadas["blanda"][habilidad] = nueva["nombre"]

    criterios = await obtener_config(db)
    criterios_visibles = formatear_criterios(criterios)

    return templates.TemplateResponse("probar.html", {
        "request": request,
        "crear_tecnica": crear_tecnica,
        "crear_blanda": crear_blanda,
        "habilidad_tecnica_generada": habilidad_tecnica_generada,
        "habilidad_blanda_generada": habilidad_blanda_generada,
        "nuevas_subs_tecnicas": nuevas_subs_tecnicas,
        "nuevas_subs_blandas": nuevas_subs_blandas,
        "subtematicas_generadas": subtematicas_generadas,
        "criterios": criterios_visibles
    })

@router.get("/escoger", response_class=HTMLResponse)
async def escoger_formulario(request: Request):
    return templates.TemplateResponse("escoger.html", {"request": request})

@router.post("/escoger", response_class=HTMLResponse)
async def procesar_seleccion(
    request: Request,
    cantidad: int = Form(...),
    tipo: str = Form(...),
    user_id: str = Depends(get_current_user_id)
):
    if not user_id:
        return RedirectResponse(url="/auth/login")

    seleccionadas = await escoger_habilidades_subtematica(db, user_id, tipo, cantidad)
    return templates.TemplateResponse("escoger.html", {
        "request": request,
        "seleccionadas": seleccionadas,
        "cantidad": cantidad,
        "tipo": tipo
    })

@router.get("/codigo", response_class=HTMLResponse)
async def ver_lenguajes_codigo(request: Request, user_id: str = Depends(get_current_user_id)):
    if not user_id:
        return RedirectResponse(url="/auth/login")

    print(f"user id: {user_id}")
    lenguajes = await detectar_lenguajes_perfil(db, user_id)

    return templates.TemplateResponse("codigo.html", {
        "request": request,
        "lenguajes": lenguajes
    })