from utils.codigo import evaluar_respuesta_codigo, orquestar_pregunta_codigo
from bson import ObjectId
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, Path
from db.mongo import db
from services.llm import evaluar_respuesta_llm
from utils.audio import evaluar_analisis_audio
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
        

    preguntasTec = await db["preguntas"].find({
        "entrevista_id": ObjectId(entrevista_id),
        "tipo": "tecnica"
    }).to_list(length=None)

    preguntaTec_ids = [p["_id"] for p in preguntasTec]
    respuestasTec = await db["respuestas"].find({
        "pregunta_id": {"$in": preguntaTec_ids}
    }).to_list(length=None)

    for respuesta in respuestasTec:
        if "respuesta_texto" in respuesta and "evaluacion_llm" not in respuesta:
            try:
                pregunta_doc = await db["preguntas"].find_one({"_id": ObjectId(respuesta["pregunta_id"])})
                pregunta_texto = pregunta_doc.get("pregunta", "") if pregunta_doc else ""

                evaluacion = await evaluar_respuesta_llm(pregunta_texto, respuesta["respuesta_texto"])

                await db["respuestas"].update_one(
                    {"_id": respuesta["_id"]},
                    {"$set": {"evaluacion_llm": evaluacion}}
                )
                print(f"Evaluada respuesta: {respuesta['_id']}")

                audio_eval = evaluar_analisis_audio(respuesta.get("analisis_audio", {}))

                await db["respuestas"].update_one(
                    {"_id": respuesta["_id"]},
                    {"$set": {
                        "evaluacion_audio": audio_eval["evaluacion_audio"],
                        "puntaje_audio": audio_eval["puntaje_audio"]
                    }}
                )

            except Exception as e:
                print(f"Error evaluando respuesta con LLM: {e}")

    preguntasBla = await db["preguntas"].find({
        "entrevista_id": ObjectId(entrevista_id),
        "tipo": "blanda"
    }).to_list(length=None)

    preguntaBla_ids = [p["_id"] for p in preguntasBla]
    respuestasBla = await db["respuestas"].find({
        "pregunta_id": {"$in": preguntaBla_ids}
    }).to_list(length=None)

    for respuesta in respuestasBla:
        if "respuesta_texto" in respuesta and "evaluacion_llm" not in respuesta:
            try:
                pregunta_doc = await db["preguntas"].find_one({"_id": ObjectId(respuesta["pregunta_id"])})
                pregunta_texto = pregunta_doc.get("pregunta", "") if pregunta_doc else ""

                evaluacion = await evaluar_respuesta_llm(pregunta_texto, respuesta["respuesta_texto"])

                await db["respuestas"].update_one(
                    {"_id": respuesta["_id"]},
                    {"$set": {"evaluacion_llm": evaluacion}},
                )

                await db["respuestas"].update_one(
                    {"_id": respuesta["_id"]},
                    {"$set": {
                        "evaluacion_audio": audio_eval["evaluacion_audio"],
                        "puntaje_audio": audio_eval["puntaje_audio"]
                    }}
                )

            except Exception as e:
                print(f"Error evaluando respuesta con LLM: {e}")

    
    respuestas = await db["respuestas"].find({
        "pregunta_id": {"$in": pregunta_ids}
    }).to_list(length=None)

    respuestasTec = await db["respuestas"].find({
        "pregunta_id": {"$in": preguntaTec_ids}
    }).to_list(length=None)

    respuestasBla = await db["respuestas"].find({
        "pregunta_id": {"$in": preguntaBla_ids}
    }).to_list(length=None)

    return templates.TemplateResponse("resultados.html", {
        "request": request,
        "usuario": payload,
        "entrevista": entrevista,
        "preguntas": preguntas,
        "respuestas": respuestas,
        "preguntasTec": preguntasTec,
        "respuestasTec": respuestasTec,
        "preguntasBla": preguntasBla,
        "respuestasBla": respuestasBla
    })


@router.get("/dashboard", response_class=HTMLResponse)
async def mostrar_dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")

    from auth.auth import decode_token
    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/auth/login")

    usuario_id = payload.get("user_id")

    entrevistas = await db["entrevistas"].find({"usuario_id": ObjectId(usuario_id)}).to_list(length=None)

    entrevistas_con_detalles = []
    for entrevista in entrevistas:
        entrevista_id = entrevista["_id"]

        preguntas = await db["preguntas"].find({"entrevista_id": entrevista_id}).to_list(length=None)
        total = len(preguntas)
        codigos = sum(1 for p in preguntas if p["tipo"] == "codigo")
        tecnicas = sum(1 for p in preguntas if p["tipo"] == "tecnica")
        blandas = sum(1 for p in preguntas if p["tipo"] == "blanda")

        respuestas = await db["respuestas"].find({"entrevista_id": entrevista_id}).to_list(length=None)

        puntajes_llm = [r["evaluacion_llm"]["puntaje"] for r in respuestas if r.get("evaluacion_llm")]
        puntajes_audio = [r["puntaje_audio"] for r in respuestas if r.get("puntaje_audio")]

        promedio_llm = sum(puntajes_llm) / len(puntajes_llm) if puntajes_llm else None
        promedio_audio = sum(puntajes_audio) / len(puntajes_audio) if puntajes_audio else None

        entrevistas_con_detalles.append({
            "_id": str(entrevista_id),
            "fecha": entrevista.get("fecha_inicio").strftime("%Y-%m-%d %H:%M"),
            "total": total,
            "codigo": codigos,
            "tecnica": tecnicas,
            "blanda": blandas,
            "estado": entrevista.get("estado", "desconocido"),
            "promedio_llm": round(promedio_llm, 1) if promedio_llm else "N/A",
            "promedio_audio": round(promedio_audio, 1) if promedio_audio else "N/A"
        })

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": payload,
        "entrevistas": entrevistas_con_detalles
    })
