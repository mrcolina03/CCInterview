from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId
from db.mongo import db
from auth.dependencies import get_current_user
from utils.perfil_usuario import crear_perfil_usuario
import os

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/cv"))

@router.get("/create", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse("create.html", {"request": request})

@router.post("/submit")
async def submit_form(
    request: Request,
    user: dict = Depends(get_current_user),
    nombre: str = Form(...),
    lenguajes: str = Form(...),
    frameworks: str = Form(""),
    bases_datos: str = Form(""),
    herramientas: str = Form(""),
    exp_puesto: list[str] = Form(default=[]),
    exp_empresa: list[str] = Form(default=[]),
    exp_duracion: list[str] = Form(default=[]),
    exp_descripcion: list[str] = Form(default=[]),
    cert_nombre: list[str] = Form(default=[]),
    cert_emisor: list[str] = Form(default=[]),
    idioma_nombre: list[str] = Form(default=[]),
    idioma_nivel: list[str] = Form(default=[]),
    estudio_institucion: list[str] = Form(default=[]),
    estudio_titulo: list[str] = Form(default=[]),
    estudio_anios: list[str] = Form(default=[])
):
    user_id = user["sub"]

    experiencia = [
        {
            "puesto": exp_puesto[i],
            "empresa": exp_empresa[i],
            "duracion": exp_duracion[i],
            "descripcion": exp_descripcion[i]
        } for i in range(len(exp_puesto))
    ]

    certificaciones = [
        {
            "nombre": cert_nombre[i],
            "emisor": cert_emisor[i]
        } for i in range(len(cert_nombre))
    ]

    idiomas = [
        {
            "nombre": idioma_nombre[i],
            "nivel": idioma_nivel[i]
        } for i in range(len(idioma_nombre))
    ]

    estudios = [
        {
            "institucion": estudio_institucion[i],
            "titulo": estudio_titulo[i],
            "anios": estudio_anios[i]
        } for i in range(len(estudio_institucion))
    ]

    curriculum = {
        "usuario_id": ObjectId(user_id),
        "nombre": nombre,
        "habilidades_tecnicas": {
            "lenguajes": lenguajes,
            "frameworks": frameworks,
            "bases_datos": bases_datos,
            "herramientas": herramientas,
        },
        "experiencia": experiencia,
        "certificaciones": certificaciones,
        "idiomas": idiomas,
        "estudios": estudios
    }

    try:
        perfil_usuario = await crear_perfil_usuario(curriculum)
        result_cv = await db["curriculum"].insert_one(curriculum)
        perfil_documento = {
            "usuario_id": ObjectId(user_id),
            **perfil_usuario
        }
        await db["perfil_usuario"].insert_one(perfil_documento)

    except Exception as e:
        print(f"Error al guardar CV o generar perfil: {e}")
        if "result_cv" in locals() and result_cv.inserted_id:
            await db["curriculum"].delete_one({"_id": result_cv.inserted_id})
        return templates.TemplateResponse("mensaje4.html", {
            "request": request,
            "mensaje": "Ocurrió un error y no se guardaron los datos."
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "mensaje": "CV y perfil guardados exitosamente.",
        "cv": curriculum
    })

@router.get("/index", response_class=HTMLResponse)
async def perfil_usuario(request: Request, user: dict = Depends(get_current_user)):
    user_id = user["sub"]

    cv = await db["curriculum"].find_one({"usuario_id": ObjectId(user_id)})

    if not cv:
        return templates.TemplateResponse("mensaje3.html", {
            "request": request,
            "mensaje": "Aún no has registrado tu CV."
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "cv": cv
    })
