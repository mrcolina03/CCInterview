import base64
import json
import io
from fastapi import APIRouter, Request, Form, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from bson import ObjectId
from auth.auth import decode_token
from db.mongo import db
import os
from utils.preguntas import generar_preguntas_para_entrevista
from utils.audio import procesar_audio_base64
from services.transcripcion import transcribir_audio
from services.llm import evaluar_respuesta_llm
from utils.codigo import asegurar_plantilla_codigo
from utils.adaptabilidad import detectar_lenguajes_perfil

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates/entrevista"))

@router.get("/nueva", response_class=HTMLResponse)
async def mostrar_formulario_nueva_entrevista(request: Request):
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

    config = await db["config"].find_one({"_id": "duraciones"})
    if not config:
        config = {
            "corta": {"minutos": 20},
            "mediana": {"minutos": 40},
            "larga": {"minutos": 60}
        }

    return templates.TemplateResponse("nueva.html", {
        "request": request,
        "config": config,
        "nombre": nombre
    })

@router.post("/nueva")
async def crear_entrevista(
    request: Request,
    duracion: str = Form(...),
    modo: str = Form(...)
):
    token = request.cookies.get("access_token")
    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/auth/login")
    
    cv = await db["curriculum"].find_one({"usuario_id": ObjectId(payload.get("sub"))})
    if not cv:
        return RedirectResponse(url="/?error=no_cv", status_code=302)

    usuario_id = payload.get("sub")
    
    await detectar_lenguajes_perfil(db, usuario_id)

    config_doc = await db["config"].find_one({"_id": "duraciones"})
    if not config_doc or duracion not in config_doc:
        return RedirectResponse(url="/entrevista/nueva")

    config = config_doc[duracion]

    # Asignación de preguntas según el modo
    preguntas_tecnicas = 0
    preguntas_blandas = 0
    preguntas_codigo = 0

    if modo == "mixto":
        preguntas_tecnicas = config.get("tecnicas", 0)
        preguntas_blandas = config.get("blandas", 0)
        preguntas_codigo = config.get("codigo", 0)
    elif modo == "solo tecnica":
        preguntas_tecnicas = config.get("preguntas", 0)
    elif modo == "solo blanda":
        preguntas_blandas = config.get("preguntas", 0)
    elif modo == "codigo":
        preguntas_codigo = config.get("preguntas", 0)

    entrevista = {
        "usuario_id": ObjectId(usuario_id),
        "fecha_inicio": datetime.utcnow(),
        "fecha_fin": None,
        "estado": "en_progreso",
        "modo": modo,
        "duracion_min": config["minutos"],
        "num_preguntas": preguntas_tecnicas + preguntas_blandas + preguntas_codigo,
        "preguntas_tecnicas": preguntas_tecnicas,
        "preguntas_blandas": preguntas_blandas,
        "preguntas_codigo": preguntas_codigo,
    }

    resultado = await db["entrevistas"].insert_one(entrevista)
    entrevista_id = str(resultado.inserted_id)
    await generar_preguntas_para_entrevista(db, entrevista_id)

    # Redirigir al layout de preguntas
    return RedirectResponse(url=f"/entrevista/preguntas/{entrevista_id}", status_code=302)

@router.get("/preguntas/{entrevista_id}", response_class=HTMLResponse)
async def mostrar_entrevista(request: Request, entrevista_id: str):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")

    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/auth/login")
    

    entrevista = await db["entrevistas"].find_one({"_id": ObjectId(entrevista_id)})
    if not entrevista:
        return RedirectResponse(url="/")

    preguntas = await db["preguntas"].find({
        "entrevista_id": ObjectId(entrevista_id)
    }).to_list(length=None)
    

    respuestas = await db["respuestas"].find({
        "pregunta_id": {"$in": [p["_id"] for p in preguntas]}
    }).to_list(length=None)
    #print(f"Respuestas obtenidas: {respuestas}")

    ids_respondidas = {r["pregunta_id"] for r in respuestas}
    preguntas_no_respondidas = [p for p in preguntas if p["_id"] not in ids_respondidas]
    
     # Si ya no hay preguntas por responder, redirigir a feedback
    if not preguntas_no_respondidas:
        return RedirectResponse(url=f"/feedback/resultados/{entrevista_id}", status_code=302)

    pregunta_actual = preguntas_no_respondidas[0] if preguntas_no_respondidas else None
    terminada = pregunta_actual is None
    
    
     # Obtener plantillas desde config solo si es pregunta tipo código
    plantillas = {}
    if pregunta_actual["tipo"] == "codigo":
        lenguaje = pregunta_actual.get("lenguaje").lower()
        await asegurar_plantilla_codigo(db, lenguaje)

        config_doc = await db["config"].find_one({"_id": "plantillas_codigo"})
        plantillas = config_doc.get("plantillas", {}) if config_doc else {}

    # Si se desea reanudar: usa "tiempo_restante" si existe
    terminada = entrevista.get("estado") == "terminada"
    
    duracion_total = entrevista["duracion_min"] * 60
    tiempo_restante = entrevista.get("tiempo_restante", duracion_total)
    
    # No pasar tiempo si ya está terminada
    tiempo_mostrar = tiempo_restante if not terminada else 0

    return templates.TemplateResponse("preguntas.html", {
        "request": request,
        "entrevista_id": entrevista_id,
        "pregunta": pregunta_actual,
        "terminada": terminada,
        "usuario": payload,
        "plantillas": plantillas,
        "plantillas_json": json.dumps(plantillas),
        "duracion_segundos": tiempo_mostrar,
        "entrevista_estado": entrevista.get("estado", ""),
    })

@router.post("/responder/{entrevista_id}")
async def responder_pregunta_general(
    request: Request,
    entrevista_id: str = Path(...),
    pregunta_id: str = Form(...),
    respuesta: str = Form(None),
    lenguaje: str = Form(None),
    audio_data: str = Form(None)
):
    token = request.cookies.get("access_token")
    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/auth/login", status_code=302)

    usuario_id = payload.get("sub")
    doc_respuesta = {
        "entrevista_id": ObjectId(entrevista_id),
        "pregunta_id": ObjectId(pregunta_id),
        "usuario_id": ObjectId(usuario_id),
        "fecha_respuesta": datetime.utcnow()
    }

    # Caso 1: Respuesta de tipo texto o código
    if respuesta:
        doc_respuesta["respuesta"] = respuesta
        if lenguaje:
            doc_respuesta["lenguaje"] = lenguaje

    # Caso 2: Respuesta por audio (habilidades blandas)
    elif audio_data:
        analisis_audio = {}
        texto_transcrito = ""

        try:
            header, encoded = audio_data.split(",", 1)
            audio_bytes = base64.b64decode(encoded)
            audio_stream = io.BytesIO(audio_bytes)

            texto_transcrito = await transcribir_audio(audio_bytes)
            analisis_audio = await procesar_audio_base64(audio_stream)

        except Exception as e:
            print(f"Error procesando audio: {e}")
            analisis_audio = {"error": str(e)}

        pregunta_doc = await db["preguntas"].find_one({"_id": ObjectId(pregunta_id)})
        texto_pregunta = pregunta_doc.get("pregunta", "") if pregunta_doc else ""
        calificacion = await evaluar_respuesta_llm(texto_pregunta, texto_transcrito)

        doc_respuesta.update({
            "respuesta_texto": texto_transcrito,
            "analisis_audio": analisis_audio
        })

    # Insertar la respuesta (en cualquier caso)
    await db["respuestas"].insert_one(doc_respuesta)
    
    # Verificar si ya se respondieron todas las preguntas
    total = await db["preguntas"].count_documents({"entrevista_id": ObjectId(entrevista_id)})
    respondidas = await db["respuestas"].count_documents({"entrevista_id": ObjectId(entrevista_id)})

    if respondidas >= total:
        await db["entrevistas"].update_one(
            {"_id": ObjectId(entrevista_id)},
            {
                "$set": {
                    "estado": "terminada",
                    "fecha_fin": datetime.utcnow()
                },
                "$unset": {"tiempo_restante": ""}
            }
        )

    return RedirectResponse(url=f"/entrevista/preguntas/{entrevista_id}", status_code=302)

@router.post("/finalizar/{entrevista_id}")
async def finalizar_entrevista(entrevista_id: str):
    await db["entrevistas"].update_one(
        {"_id": ObjectId(entrevista_id)},
        {
            "$set": {
                "estado": "terminada",
                "fecha_fin": datetime.utcnow()
            },
            "$unset": {"tiempo_restante": ""}
        }
    )
    return {"status": "ok"}


from fastapi import Body

@router.post("/guardar-tiempo")
async def guardar_tiempo_restante(data: dict = Body(...)):
    entrevista_id = data.get("entrevista_id")
    tiempo_restante = data.get("tiempo_restante")

    if entrevista_id and tiempo_restante is not None:
        await db["entrevistas"].update_one(
            {"_id": ObjectId(entrevista_id)},
            {"$set": {"tiempo_restante": tiempo_restante}}
        )
    return {"status": "ok"}
