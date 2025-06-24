from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError
from datetime import timedelta
from urllib.parse import urlencode
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db.mongo import db
from auth.auth import hash_password, verify_password, create_access_token, decode_token
from utils.email import enviar_correo
from utils.adaptabilidad import (
    evaluar_creacion_nueva_habilidad,
    evaluar_creacion_nueva_subtematica,
    generar_nueva_habilidad,
    generar_nueva_subtematica
)
from bson import ObjectId
import os

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/auth"))

@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register_user(request: Request, email: str = Form(...), password: str = Form(...)):
    existing = await db["usuarios"].find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya existe.")

    user = {
        "email": email,
        "password_hash": hash_password(password),
        "verificado": False
    }
    result = await db["usuarios"].insert_one(user)
    user_id = str(result.inserted_id)

    # Crear token de verificación válido por 24h
    token = create_access_token({"sub": user_id}, expires_delta=timedelta(hours=24))

    # Link con token
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    link = f"{BASE_URL}/auth/verificar?token={token}"

    # Enviar correo
    html = f"""
    <h3>Verifica tu cuenta</h3>
    <p>Haz clic en el siguiente enlace para verificar tu cuenta:</p>
    <a href="{link}">{link}</a>
    """
    await enviar_correo(email, "Verifica tu cuenta", html)

    return templates.TemplateResponse("verificar.html", {"request": request, "email": email})

@router.get("/verificar", name="verificar_correo")
async def verificar_correo(request: Request, token: str):
    payload = decode_token(token)
    if not payload:
        return HTMLResponse("Token inválido o expirado.", status_code=400)

    user_id = payload.get("sub")
    await db["usuarios"].update_one({"_id": ObjectId(user_id)}, {"$set": {"verificado": True}})
    return templates.TemplateResponse("verificacion_correcta.html", {"request": request})

from fastapi import Form

@router.post("/enviar-verificacion")
async def enviar_verificacion_manual(request: Request, email: str = Form(...)):
    user = await db["usuarios"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if user.get("verificado"):
        return RedirectResponse("/auth/login", status_code=303)

    token = create_access_token({"sub": str(user["_id"])}, expires_delta=timedelta(hours=24))
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    link = f"{BASE_URL}/auth/verificar?token={token}"

    html = f"""
    <h3>Verifica tu cuenta</h3>
    <p>Haz clic en el siguiente enlace para verificar tu cuenta:</p>
    <a href="{link}">{link}</a>
    """
    await enviar_correo(user["email"], "Verifica tu cuenta", html)

    return templates.TemplateResponse("verificar.html", {"request": request, "email": email})

@router.get("/recuperar", response_class=HTMLResponse)
async def mostrar_formulario_recuperar(request: Request):
    return templates.TemplateResponse("recuperar.html", {"request": request})

@router.post("/recuperar")
async def enviar_token_recuperacion(request: Request, email: str = Form(...)):
    user = await db["usuarios"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="Correo no registrado")

    token = create_access_token({"sub": str(user["_id"])}, expires_delta=timedelta(hours=1))

    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
    link = f"{BASE_URL}/auth/cambiar-password?token={token}"


    html = f"""
    <h3>Recuperar contraseña</h3>
    <p>Haz clic en el siguiente enlace para establecer una nueva contraseña:</p>
    <a href="{link}">{link}</a>
    """
    await enviar_correo(email, "Recupera tu contraseña", html)

    return templates.TemplateResponse("correo_enviado.html", {"request": request, "email": email})

@router.get("/cambiar-password", name="cambiar_password", response_class=HTMLResponse)
async def formulario_nueva_password(request: Request, token: str):
    payload = decode_token(token)
    if not payload:
        return HTMLResponse("Token inválido o expirado.", status_code=400)

    return templates.TemplateResponse("nueva_password.html", {"request": request, "token": token})

@router.post("/cambiar-password")
async def cambiar_password(token: str = Form(...), nueva_password: str = Form(...)):
    payload = decode_token(token)
    if not payload:
        return HTMLResponse("Token inválido o expirado.", status_code=400)

    user_id = payload.get("sub")
    nuevo_hash = hash_password(nueva_password)
    await db["usuarios"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": nuevo_hash}}
    )

    return RedirectResponse("/auth/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login_user(request: Request, email: str = Form(...), password: str = Form(...)):
    try: 
        user = await db["usuarios"].find_one({"email": email})
    except (ConfigurationError, ServerSelectionTimeoutError) as e:
        return RedirectResponse(url="/?error=mongo", status_code=303)

    except Exception as e:
        return RedirectResponse(url="/?error=unexpected", status_code=303)

    
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    if not user.get("verificado"):
        return templates.TemplateResponse("reenviar_verificacion.html", {
            "request": request,
            "email": email
        })

    user_id = str(user["_id"])

    # 🔁 ADAPTABILIDAD: Evaluar y generar nuevas habilidades o subtemáticas si corresponde
    crear_tecnica = await evaluar_creacion_nueva_habilidad(db, user_id, "tecnica")
    crear_blanda = await evaluar_creacion_nueva_habilidad(db, user_id, "blanda")
    if crear_tecnica:
        await generar_nueva_habilidad(db, user_id, "tecnica")
    if crear_blanda:
        await generar_nueva_habilidad(db, user_id, "blanda")

    nuevas_subs_tecnicas = await evaluar_creacion_nueva_subtematica(db, user_id, "tecnica")
    nuevas_subs_blandas = await evaluar_creacion_nueva_subtematica(db, user_id, "blanda")

    for habilidad, debe_crear in nuevas_subs_tecnicas.items():
        if debe_crear:
            await generar_nueva_subtematica(db, user_id, habilidad, "tecnica")

    for habilidad, debe_crear in nuevas_subs_blandas.items():
        if debe_crear:
            await generar_nueva_subtematica(db, user_id, habilidad, "blanda")

    # 🔐 Crear token y redirigir
    token = create_access_token({"sub": user_id, "email": user["email"], "rol": user.get("rol", "user")})
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response
