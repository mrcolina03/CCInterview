from typing import Optional
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId
from db.mongo import db
from auth.dependencies import get_current_user
from utils.perfil_usuario import crear_perfil_usuario, eliminar_perfil
from bson import ObjectId
from auth.auth import decode_token
import os

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/cv"))

@router.get("/create", response_class=HTMLResponse)
async def form_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")

    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/auth/login")
    
    usuario_id = payload.get("sub")
    print("Payload del token:", payload)
    
    try:
        usuario_obj_id = ObjectId(usuario_id)
    except Exception:
        usuario_obj_id = usuario_id
    cv = await db["curriculum"].find_one({"usuario_id": usuario_obj_id})
    print(cv)
    nombre = cv["nombre"] if cv else "Sin nombre"
    return templates.TemplateResponse("create.html", {"request": request, "nombre": nombre})

@router.post("/submit")
async def submit_form(
    request: Request,
    user: dict = Depends(get_current_user),
    nombre: str = Form(...),
    lenguajes: str = Form(...),
    frameworks: str = Form(""),
    bases_datos: str = Form(""),
    herramientas: str = Form(""),
    # Agregar los checkboxes como campos opcionales
    no_experiencia: Optional[str] = Form(None),  # checkbox "No tengo experiencia"
    no_certificaciones: Optional[str] = Form(None),  # checkbox "No tengo certificaciones"
    # Campos de experiencia - ahora opcionales
    exp_puesto: list[str] = Form(default=[]),
    exp_empresa: list[str] = Form(default=[]),
    exp_descripcion: list[str] = Form(default=[]),
    exp_fecha_inicio: list[str] = Form(default=[]),
    exp_fecha_fin: list[str] = Form(default=[]),
    # Campos de certificaciones - ahora opcionales
    cert_nombre: list[str] = Form(default=[]),
    cert_emisor: list[str] = Form(default=[]),
    # Resto de campos (estos siguen igual)
    idioma_nombre: list[str] = Form(default=[]),
    idioma_nivel: list[str] = Form(default=[]),
    estudio_institucion: list[str] = Form(default=[]),
    estudio_titulo: list[str] = Form(default=[]),
    estudio_fecha_inicio: list[str] = Form(default=[]),
    estudio_fecha_fin: list[str] = Form(default=[])
):
    user_id = ObjectId(user["sub"])
    
    # VALIDACIÓN CONDICIONAL
    # Si no marcó "no tengo experiencia" pero no tiene experiencia, error
    if not no_experiencia and not exp_puesto:
        raise HTTPException(
            status_code=400, 
            detail="Debes agregar al menos una experiencia o marcar 'No tengo experiencia todavía'"
        )
    
    # Si no marcó "no tengo certificaciones" pero no tiene certificaciones, error
    if not no_certificaciones and not cert_nombre:
        raise HTTPException(
            status_code=400, 
            detail="Debes agregar al menos una certificación o marcar 'No tengo certificaciones todavía'"
        )
    
    # Validación de idiomas (siempre requerido)
    if not idioma_nombre:
        raise HTTPException(
            status_code=400, 
            detail="Debes agregar al menos un idioma"
        )
    
    # Validación de estudios (siempre requerido)
    if not estudio_institucion:
        raise HTTPException(
            status_code=400, 
            detail="Debes agregar al menos un estudio"
        )

    existente = await db["curriculum"].find_one({"usuario_id": user_id})

    if existente:
        form_data = {
            "nombre": nombre,
            "lenguajes": lenguajes,
            "frameworks": frameworks,
            "bases_datos": bases_datos,
            "herramientas": herramientas,
            # Agregar los flags de "no tengo"
            "no_experiencia": bool(no_experiencia),
            "no_certificaciones": bool(no_certificaciones),
            # Campos de experiencia
            "exp_puesto": exp_puesto,
            "exp_empresa": exp_empresa,
            "exp_fecha_inicio": exp_fecha_inicio,
            "exp_fecha_fin": exp_fecha_fin,
            "exp_descripcion": exp_descripcion,
            # Campos de certificaciones
            "cert_nombre": cert_nombre,
            "cert_emisor": cert_emisor,
            # Resto de campos
            "idioma_nombre": idioma_nombre,
            "idioma_nivel": idioma_nivel,
            "estudio_institucion": estudio_institucion,
            "estudio_titulo": estudio_titulo,
            "estudio_fecha_inicio": estudio_fecha_inicio,
            "estudio_fecha_fin": estudio_fecha_fin
        }
        return templates.TemplateResponse("confirmacion_cv.html", {
            "request": request,
            "form_data": form_data
        })

    # Si no existe CV, sigue el flujo normal
    return await guardar_cv_y_perfil(
        request, user, nombre, lenguajes, frameworks, bases_datos, herramientas,
        exp_puesto, exp_empresa, exp_fecha_inicio, exp_fecha_fin, exp_descripcion,
        cert_nombre, cert_emisor, idioma_nombre, idioma_nivel,
        estudio_institucion, estudio_titulo, estudio_fecha_inicio, estudio_fecha_fin,
        # Agregar los nuevos parámetros
        no_experiencia, no_certificaciones
    )

@router.post("/confirmar")
async def confirmar_cv(
    request: Request,
    user: dict = Depends(get_current_user),
    nombre: str = Form(...),
    lenguajes: str = Form(...),
    frameworks: str = Form(""),
    bases_datos: str = Form(""),
    herramientas: str = Form(""),
    # Agregar los checkboxes como campos opcionales
    no_experiencia: Optional[str] = Form(None),  # checkbox "No tengo experiencia"
    no_certificaciones: Optional[str] = Form(None),  # checkbox "No tengo certificaciones"
    # Resto de campos
    exp_puesto: list[str] = Form(default=[]),
    exp_empresa: list[str] = Form(default=[]),
    exp_fecha_inicio: list[str] = Form(default=[]),
    exp_fecha_fin: list[str] = Form(default=[]),
    exp_descripcion: list[str] = Form(default=[]),
    cert_nombre: list[str] = Form(default=[]),
    cert_emisor: list[str] = Form(default=[]),
    idioma_nombre: list[str] = Form(default=[]),
    idioma_nivel: list[str] = Form(default=[]),
    estudio_institucion: list[str] = Form(default=[]),
    estudio_titulo: list[str] = Form(default=[]),
    estudio_fecha_inicio: list[str] = Form(default=[]),
    estudio_fecha_fin: list[str] = Form(default=[])
):
    await eliminar_perfil(user)
    return await guardar_cv_y_perfil(
        request, user, nombre, lenguajes, frameworks, bases_datos, herramientas,
        exp_puesto, exp_empresa, exp_fecha_inicio, exp_fecha_fin, exp_descripcion,
        cert_nombre, cert_emisor, idioma_nombre, idioma_nivel,
        estudio_institucion, estudio_titulo, estudio_fecha_inicio, estudio_fecha_fin,
        # Agregar los nuevos parámetros
        no_experiencia, no_certificaciones
    )


@router.get("/index", response_class=HTMLResponse)
async def perfil_usuario(request: Request, user: dict = Depends(get_current_user)):
    user_id = user["sub"]

    cv = await db["curriculum"].find_one({"usuario_id": ObjectId(user_id)})
    nombre = cv["nombre"] if cv else "Sin nombre"

    
    if not cv:
        return RedirectResponse(url="/?cv=false", status_code=302)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "cv": cv,
        "nombre": nombre
    })

async def guardar_cv_y_perfil(request, user, nombre, lenguajes, frameworks, bases_datos, herramientas,
                              exp_puesto, exp_empresa, exp_fecha_inicio, exp_fecha_fin, exp_descripcion,
                              cert_nombre, cert_emisor, idioma_nombre, idioma_nivel,
                              estudio_institucion, estudio_titulo, estudio_fecha_inicio, estudio_fecha_fin, 
                              no_experiencia=None, no_certificaciones=None):
    user_id = user["sub"]

    # Manejar experiencia - solo crear si no marcó "No tengo experiencia"
    experiencia = []
    if not no_experiencia and exp_puesto:  # Si no marcó checkbox Y tiene datos
        experiencia = [
            {
                "puesto": exp_puesto[i],
                "empresa": exp_empresa[i],
                "fecha_inicio": exp_fecha_inicio[i],
                "fecha_fin": exp_fecha_fin[i],
                "descripcion": exp_descripcion[i]
            } for i in range(len(exp_puesto))
        ]

    # Manejar certificaciones - solo crear si no marcó "No tengo certificaciones"
    certificaciones = []
    if not no_certificaciones and cert_nombre:  # Si no marcó checkbox Y tiene datos
        certificaciones = [
            {
                "nombre": cert_nombre[i],
                "emisor": cert_emisor[i]
            } for i in range(len(cert_nombre))
        ]

    # Idiomas - siempre requeridos
    idiomas = [
        {
            "nombre": idioma_nombre[i],
            "nivel": idioma_nivel[i]
        } for i in range(len(idioma_nombre))
    ]

    # Estudios - siempre requeridos
    estudios = [
        {
            "institucion": estudio_institucion[i],
            "titulo": estudio_titulo[i],
            "fecha_inicio": estudio_fecha_inicio[i],
            "fecha_fin": estudio_fecha_fin[i]
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
        "estudios": estudios,
        # Agregar flags para saber si marcó "No tengo"
        "no_experiencia": bool(no_experiencia),
        "no_certificaciones": bool(no_certificaciones)
    }
    
    print(f"Curriculum a guardar: {curriculum}")
    print(f"No experiencia: {bool(no_experiencia)}")
    print(f"No certificaciones: {bool(no_certificaciones)}")

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
        return RedirectResponse(url="/?cv=error", status_code=302)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "mensaje": "CV y perfil guardado exitosamente.",
        "cv": curriculum,
        "nombre": nombre
    })
