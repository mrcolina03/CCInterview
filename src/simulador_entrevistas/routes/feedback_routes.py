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
    usuario_id = payload.get("sub")
    print("Payload del token:", payload)
    try:
        usuario_obj_id = ObjectId(usuario_id)
    except Exception:
        usuario_obj_id = usuario_id
    entrevistas = await db["entrevistas"].find({"usuario_id": usuario_obj_id}).to_list(length=None)
    print(f"Entrevistas encontradas para usuario {usuario_id}: {len(entrevistas)}")
    entrevistas_con_detalles = []
    
    for entrevista in entrevistas:
        entrevista_id = entrevista["_id"]
        preguntas = await db["preguntas"].find({"entrevista_id": entrevista_id}).to_list(length=None)
        respuestas = await db["respuestas"].find({"entrevista_id": entrevista_id}).to_list(length=None)
        print(f"Entrevista {entrevista_id} tiene {len(preguntas)} preguntas y {len(respuestas)} respuestas")
        
        if not preguntas and not respuestas:
            continue  # Saltar entrevistas sin datos reales
        
        # Crear mapas para facilitar búsquedas
        preguntas_map = {str(p["_id"]): p for p in preguntas}
        
        total = len(preguntas)
        codigos = sum(1 for p in preguntas if p.get("tipo") == "codigo")
        tecnicas = sum(1 for p in preguntas if p.get("tipo") == "tecnica")
        blandas = sum(1 for p in preguntas if p.get("tipo") == "blanda")
        
        # Calcular promedios por tipo de pregunta
        puntajes_codigo = []
        puntajes_tecnica = []
        puntajes_blanda = []
        
        for respuesta in respuestas:
            pregunta_id = str(respuesta.get("pregunta_id"))
            pregunta = preguntas_map.get(pregunta_id)
            
            if not pregunta:
                continue
                
            tipo_pregunta = pregunta.get("tipo")
            
            # Obtener puntaje según el tipo de evaluación
            puntaje = None
            if respuesta.get("evaluacion_llm"):
                puntaje = respuesta["evaluacion_llm"].get("puntaje")
            elif respuesta.get("puntaje_audio") is not None:
                puntaje = respuesta["puntaje_audio"]
            elif respuesta.get("feedback"):
                puntaje = respuesta["feedback"].get("puntuacion")
            
            # Clasificar por tipo de pregunta
            if puntaje is not None:
                if tipo_pregunta == "codigo":
                    puntajes_codigo.append(puntaje)
                elif tipo_pregunta == "tecnica":
                    puntajes_tecnica.append(puntaje)
                elif tipo_pregunta == "blanda":
                    puntajes_blanda.append(puntaje)
        
        # Calcular promedios
        promedio_codigo = round(sum(puntajes_codigo) / len(puntajes_codigo), 1) if puntajes_codigo else "N/A"
        promedio_tecnica = round(sum(puntajes_tecnica) / len(puntajes_tecnica), 1) if puntajes_tecnica else "N/A"
        promedio_blanda = round(sum(puntajes_blanda) / len(puntajes_blanda), 1) if puntajes_blanda else "N/A"
        
        entrevistas_con_detalles.append({
            "_id": str(entrevista_id),
            "fecha": entrevista.get("fecha_inicio").strftime("%Y-%m-%d %H:%M") if entrevista.get("fecha_inicio") else "Sin fecha",
            "total": total,
            "codigo": codigos,
            "tecnica": tecnicas,
            "blanda": blandas,
            "estado": entrevista.get("estado", "desconocido"),
            "promedio_codigo": promedio_codigo,
            "promedio_tecnica": promedio_tecnica,
            "promedio_blanda": promedio_blanda
        })
    
    print("Entrevistas con detalles:", entrevistas_con_detalles)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": payload,
        "entrevistas": entrevistas_con_detalles
    })

@router.get("/ver-resultados/{entrevista_id}", response_class=HTMLResponse)
async def ver_resultados(request: Request, entrevista_id: str = Path(...)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")

    from auth.auth import decode_token
    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/auth/login")

    # Verificar que la entrevista existe
    entrevista = await db["entrevistas"].find_one({"_id": ObjectId(entrevista_id)})
    if not entrevista:
        return RedirectResponse(url="/")

    # Obtener preguntas de código
    preguntas = await db["preguntas"].find({
        "entrevista_id": ObjectId(entrevista_id),
        "tipo": "codigo"
    }).to_list(length=None)

    pregunta_ids = [p["_id"] for p in preguntas]
    respuestas = await db["respuestas"].find({
        "pregunta_id": {"$in": pregunta_ids}
    }).to_list(length=None)

    # Obtener preguntas técnicas
    preguntasTec = await db["preguntas"].find({
        "entrevista_id": ObjectId(entrevista_id),
        "tipo": "tecnica"
    }).to_list(length=None)

    preguntaTec_ids = [p["_id"] for p in preguntasTec]
    respuestasTec = await db["respuestas"].find({
        "pregunta_id": {"$in": preguntaTec_ids}
    }).to_list(length=None)

    # Obtener preguntas blandas
    preguntasBla = await db["preguntas"].find({
        "entrevista_id": ObjectId(entrevista_id),
        "tipo": "blanda"
    }).to_list(length=None)

    preguntaBla_ids = [p["_id"] for p in preguntasBla]
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
