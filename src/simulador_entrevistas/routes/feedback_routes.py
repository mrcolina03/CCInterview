from utils.codigo import evaluar_respuesta_codigo, orquestar_pregunta_codigo
from bson import ObjectId
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter, Request, Path
from db.mongo import db
from services.llm import evaluar_respuesta_llm
from utils.audio import evaluar_analisis_audio
from pymongo import DESCENDING
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
    entrevistas = await db["entrevistas"].find({"usuario_id": usuario_obj_id}).sort("fecha_inicio", DESCENDING).to_list(length=None)
    entrevistas_con_detalles = []
    cv = await db["curriculum"].find_one({"usuario_id": usuario_obj_id})
    print(cv)
    nombre = cv["nombre"] if cv else "Sin nombre"

    
    for entrevista in entrevistas:
        entrevista_id = entrevista["_id"]
        preguntas = await db["preguntas"].find({"entrevista_id": entrevista_id}).to_list(length=None)
        respuestas = await db["respuestas"].find({"entrevista_id": entrevista_id}).to_list(length=None)
        
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
    totales = {
    "total_entrevistas": len(entrevistas_con_detalles),
    "total_codigo": sum(e["codigo"] for e in entrevistas_con_detalles),
    "total_tecnica": sum(e["tecnica"] for e in entrevistas_con_detalles),
    "total_blanda": sum(e["blanda"] for e in entrevistas_con_detalles),
    "total_preguntas": sum(e["total"] for e in entrevistas_con_detalles)
    }
    todos_puntajes_codigo = []
    todos_puntajes_tecnica = []
    todos_puntajes_blanda = []

    for entrevista in entrevistas_con_detalles:
        if entrevista["promedio_codigo"] != "N/A":
            todos_puntajes_codigo.append(entrevista["promedio_codigo"])
        if entrevista["promedio_tecnica"] != "N/A":
            todos_puntajes_tecnica.append(entrevista["promedio_tecnica"])
        if entrevista["promedio_blanda"] != "N/A":
            todos_puntajes_blanda.append(entrevista["promedio_blanda"])

    # Calcular promedios generales
    totales["promedio_general_codigo"] = round(sum(todos_puntajes_codigo) / len(todos_puntajes_codigo), 1) if todos_puntajes_codigo else "N/A"
    totales["promedio_general_tecnica"] = round(sum(todos_puntajes_tecnica) / len(todos_puntajes_tecnica), 1) if todos_puntajes_tecnica else "N/A"
    totales["promedio_general_blanda"] = round(sum(todos_puntajes_blanda) / len(todos_puntajes_blanda), 1) if todos_puntajes_blanda else "N/A"
    print("Entrevistas con detalles:", entrevistas_con_detalles)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": payload,
        "entrevistas": entrevistas_con_detalles,
        "totales": totales,
        "nombre": nombre
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

    return templates.TemplateResponse("ver-resultados.html", {
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



@router.get("/progreso", response_class=HTMLResponse)
async def mostrar_progreso(request: Request):
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
    cv = await db["curriculum"].find_one({"usuario_id": usuario_obj_id})
    print(cv)
    nombre = cv["nombre"] if cv else "Sin nombre"
    
    # Obtener entrevistas ordenadas por fecha
    entrevistas = await db["entrevistas"].find(
        {"usuario_id": usuario_obj_id}
    ).sort("fecha_inicio", 1).to_list(length=None)
    
    print(f"Entrevistas encontradas para usuario {usuario_id}: {len(entrevistas)}")
    
    datos_progreso = []
    
    for entrevista in entrevistas:
        entrevista_id = entrevista["_id"]
        preguntas = await db["preguntas"].find({"entrevista_id": entrevista_id}).to_list(length=None)
        respuestas = await db["respuestas"].find({"entrevista_id": entrevista_id}).to_list(length=None)
        
        # Saltar entrevistas sin datos
        if not preguntas and not respuestas:
            continue
        
        # Crear mapas para facilitar búsquedas
        preguntas_map = {str(p["_id"]): p for p in preguntas}
        
        # Listas para almacenar puntajes por tipo
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
        
        # Calcular promedios para esta entrevista
        promedio_codigo = round(sum(puntajes_codigo) / len(puntajes_codigo), 1) if puntajes_codigo else None
        promedio_tecnica = round(sum(puntajes_tecnica) / len(puntajes_tecnica), 1) if puntajes_tecnica else None
        promedio_blanda = round(sum(puntajes_blanda) / len(puntajes_blanda), 1) if puntajes_blanda else None
        
        # Solo agregar si tiene al menos un promedio
        if promedio_codigo is not None or promedio_tecnica is not None or promedio_blanda is not None:
            fecha_formateada = entrevista.get("fecha_inicio").strftime("%Y-%m-%d") if entrevista.get("fecha_inicio") else "Sin fecha"
            
            datos_progreso.append({
                "entrevista_id": str(entrevista_id),
                "fecha": fecha_formateada,
                "fecha_display": entrevista.get("fecha_inicio").strftime("%d/%m/%Y") if entrevista.get("fecha_inicio") else "Sin fecha",
                "promedio_codigo": promedio_codigo,
                "promedio_tecnica": promedio_tecnica,
                "promedio_blanda": promedio_blanda,
                "total_preguntas": len(preguntas),
                "total_codigo": len(puntajes_codigo),
                "total_tecnica": len(puntajes_tecnica),
                "total_blanda": len(puntajes_blanda)
            })
    
    # Estadísticas generales
    estadisticas = {
        "total_entrevistas": len(datos_progreso),
        "fechas": [d["fecha"] for d in datos_progreso],
        "promedios_codigo": [d["promedio_codigo"] for d in datos_progreso if d["promedio_codigo"] is not None],
        "promedios_tecnica": [d["promedio_tecnica"] for d in datos_progreso if d["promedio_tecnica"] is not None],
        "promedios_blanda": [d["promedio_blanda"] for d in datos_progreso if d["promedio_blanda"] is not None]
    }
    
    # Calcular tendencias
    if estadisticas["promedios_codigo"]:
        estadisticas["tendencia_codigo"] = "" if len(estadisticas["promedios_codigo"]) > 1 and estadisticas["promedios_codigo"][-1] > estadisticas["promedios_codigo"][0] else ""
        estadisticas["mejor_codigo"] = max(estadisticas["promedios_codigo"])
        estadisticas["promedio_general_codigo"] = round(sum(estadisticas["promedios_codigo"]) / len(estadisticas["promedios_codigo"]), 1)
    
    if estadisticas["promedios_tecnica"]:
        estadisticas["tendencia_tecnica"] = "" if len(estadisticas["promedios_tecnica"]) > 1 and estadisticas["promedios_tecnica"][-1] > estadisticas["promedios_tecnica"][0] else ""
        estadisticas["mejor_tecnica"] = max(estadisticas["promedios_tecnica"])
        estadisticas["promedio_general_tecnica"] = round(sum(estadisticas["promedios_tecnica"]) / len(estadisticas["promedios_tecnica"]), 1)
    
    if estadisticas["promedios_blanda"]:
        estadisticas["tendencia_blanda"] = "" if len(estadisticas["promedios_blanda"]) > 1 and estadisticas["promedios_blanda"][-1] > estadisticas["promedios_blanda"][0] else ""
        estadisticas["mejor_blanda"] = max(estadisticas["promedios_blanda"])
        estadisticas["promedio_general_blanda"] = round(sum(estadisticas["promedios_blanda"]) / len(estadisticas["promedios_blanda"]), 1)
    
    print("Datos de progreso:", datos_progreso)
    print("Estadísticas:", estadisticas)
    
    return templates.TemplateResponse("progreso.html", {
        "request": request,
        "usuario": payload,
        "datos_progreso": datos_progreso,
        "estadisticas": estadisticas,
        "nombre": nombre
    })
