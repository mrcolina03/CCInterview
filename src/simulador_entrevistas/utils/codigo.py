from services.compilator import obtener_lenguajes_judge0, ejecutar_codigo_judge0
from services.llm import evaluar_codigo_llm, generar_boilerplate_lenguaje
from bson import ObjectId

# Cache local de lenguaje a ID
LANGUAGE_MAP = {}

async def inicializar_mapeo_lenguajes():
    global LANGUAGE_MAP
    lenguajes = await obtener_lenguajes_judge0()
    LANGUAGE_MAP = {l["name"].lower(): l["id"] for l in lenguajes}
    print(f"Lenguajes disponibles en Judge0: {LANGUAGE_MAP}")


# Generar y guardar plantilla en config si no existe
async def asegurar_plantilla_codigo(db, lenguaje_nombre: str):
    lenguaje_nombre = lenguaje_nombre.lower()
    plantilla_doc = await db["config"].find_one({"_id": "plantillas_codigo"})
    if not plantilla_doc:
        plantilla_doc = {"_id": "plantillas_codigo", "plantillas": {}}

    if lenguaje_nombre not in plantilla_doc.get("plantillas", {}):
        boilerplate = await generar_boilerplate_lenguaje(lenguaje_nombre)
        plantilla_doc["plantillas"][lenguaje_nombre] = boilerplate
        await db["config"].update_one(
            {"_id": "plantillas_codigo"},
            {"$set": {"plantillas": plantilla_doc["plantillas"]}},
            upsert=True
        )
        print(f"Plantilla para '{lenguaje_nombre}' generada y almacenada")


# Ejecutar y guardar resultado
async def evaluar_respuesta_codigo(db, respuesta_id: str):
    respuesta = await db["respuestas"].find_one({"_id": ObjectId(respuesta_id)})
    if not respuesta:
        print(f"Respuesta con ID {respuesta_id} no encontrada")
        return {"error": "Respuesta no encontrada"}

    lenguaje_nombre = respuesta["lenguaje"].lower()
    
    if not LANGUAGE_MAP:
        await inicializar_mapeo_lenguajes()
        print("Mapeo de lenguajes inicializado")

    lenguaje_id = next(
        (lid for nombre, lid in LANGUAGE_MAP.items() if lenguaje_nombre in nombre),
        None
    )
    print(f"Lenguaje solicitado: {lenguaje_nombre} (ID: {lenguaje_id})")
    if not lenguaje_id:
        return {"error": f"Lenguaje '{lenguaje_nombre}' no soportado por Judge0"}
    
    if lenguaje_nombre != "1. otro":
            print("Lenguaje 'Otro' no soportado por Judge0")
            ejecucion = await ejecutar_codigo_judge0(respuesta["respuesta"], lenguaje_id)

    salida = ejecucion.get("stdout")
    error = ejecucion.get("stderr") or ejecucion.get("compile_output")

    await db["respuestas"].update_one(
        {"_id": ObjectId(respuesta_id)},
        {"$set": {
            "salida": salida.strip() if salida else None,
            "error": error.strip() if error else None,
            "estado": ejecucion.get("status", {}).get("description")
        }}
    )

    return {
        "salida": salida,
        "error": error,
        "estado": ejecucion.get("status", {}).get("description")
    }


async def orquestar_pregunta_codigo(db, respuesta_id: str):
    respuesta = await db["respuestas"].find_one({"_id": ObjectId(respuesta_id)})
    if not respuesta:
        print("Respuesta no encontrada")
        return None

    pregunta = await db["preguntas"].find_one({"_id": respuesta["pregunta_id"]})
    if not pregunta:
        print("Pregunta no encontrada")
        return None

    feedback = await evaluar_codigo_llm(
        problema=pregunta["pregunta"],
        codigo_usuario=respuesta["respuesta"],
        salida=respuesta.get("salida"),
        error=respuesta.get("error"),
        estado=respuesta.get("estado", "Desconocido")
    )

    if not feedback:
        print("Feedback no generado por LLM")
        return None

    await db["respuestas"].update_one(
        {"_id": ObjectId(respuesta_id)},
        {"$set": {"feedback": feedback}}
    )
    return feedback
