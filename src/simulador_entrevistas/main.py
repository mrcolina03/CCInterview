from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routes.cv_routes import router as cv_router
from routes.auth_routes import router as auth_router
from routes.entrevista_routes import router as entrevista_router
from routes.config_routes import router as config_router
from routes.adaptabilidad_routes import router as adaptabilidad_router
from routes.feedback_routes import router as feedback_router

from auth.auth import decode_token  # Importa la función para decodificar el token
import os

app = FastAPI(title="Simulador de Entrevistas")

app.include_router(cv_router, prefix="/cv")
app.include_router(auth_router, prefix="/auth")
app.include_router(entrevista_router, prefix="/entrevista")
app.include_router(config_router, prefix="/config")
app.include_router(adaptabilidad_router, prefix="/adaptabilidad")
app.include_router(feedback_router, prefix="/feedback")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, cv: Optional[str] = None, error: Optional[str] = None):
    token = request.cookies.get("access_token")
    user = None

    if token:
        payload = decode_token(token)
        if payload:
            user = {"id": payload.get("sub"), "email": payload.get("email"), "rol": payload.get("rol")}

    mensaje = None
    if cv == "false":
        mensaje = "Aún no has registrado tu CV."
    
    if cv == "error":
        mensaje = "Ha ocurrido un error. Vuelve a intentarlo"
        
    if error == "no_cv":
        mensaje = "No se ha encontrado un CV asociado a tu cuenta. Por favor, crea uno antes de continuar."
        
    if error== "mongo":
        mensaje = "Error al conectar con la base de datos. Por favor, inténtalo más tarde."
    elif error == "unexpected":
        mensaje = "Ha ocurrido un error inesperado. Por favor, inténtalo más tarde."
        
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "mensaje": mensaje   })

# Ruta para cerrar sesión
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response
