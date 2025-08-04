from services.llm import generar_pregunta_llm, generar_problema_codigo_llm
from services.embeddings import vectorizar_texto, similitud_coseno
from utils.adaptabilidad import obtener_perfil_usuario, escoger_habilidades_subtematica, escoger_lenguaje
from bson import ObjectId

UMBRAL_SIMILITUD = 0.92  # ajustable

async def generar_y_guardar_pregunta(db, entrevista: dict, tipo: str, habilidad: str, subtematica: str):
    print(f"Generando pregunta para tipo: {tipo}, habilidad: {habilidad}, subtemática: {subtematica}")
    perfil = await obtener_perfil_usuario(db, str(entrevista["usuario_id"]))
    habilidad_data = next((h for h in perfil["tematicas_a_evaluar"] if h["habilidad"] == habilidad), None)
    if not habilidad_data:
        print("No se encontró habilidad_data")
        return None

    nivel = habilidad_data.get("nivel_esperado", "basico")
    clasificacion = perfil.get("clasificacion_junior", "desconocido")

    for intento in range(10):
        print(f"Intento {intento + 1} de generación")
        texto_pregunta = await generar_pregunta_llm(clasificacion, tipo, habilidad, nivel, subtematica)
        print("Texto generado:", texto_pregunta)

        if not texto_pregunta:
            continue

        embedding = await vectorizar_texto(texto_pregunta)
        if not embedding:
            print("Embedding fallido")
            continue

        preguntas_previas = await db["preguntas"].find({
            "usuario_id": entrevista["usuario_id"],
            "habilidad": habilidad,
            "subtematica": subtematica,
            "tipo": tipo
        }).to_list(200)

        duplicada = any(
            similitud_coseno(p["vector_embedding"], embedding) > UMBRAL_SIMILITUD
            for p in preguntas_previas
            if "vector_embedding" in p
        )
        print("¿Pregunta duplicada?", duplicada)

        if not duplicada:
            pregunta_doc = {
                "tipo": tipo,
                "habilidad": habilidad,
                "subtematica": subtematica,
                "pregunta": texto_pregunta,
                "vector_embedding": embedding,
                "entrevista_id": entrevista["_id"],
                "usuario_id": entrevista["usuario_id"],  # ahora se agrega explícitamente
                "respuesta": None
            }
            await db["preguntas"].insert_one(pregunta_doc)
            print("Pregunta insertada en BD")
            return pregunta_doc

    print("No se pudo generar pregunta distinta tras 5 intentos")
    return None

async def generar_preguntas_para_entrevista(db, entrevista_id: str):
    entrevista = await db["entrevistas"].find_one({"_id": ObjectId(entrevista_id)})
    if not entrevista:
        print("No se pudo obtener la entrevista actual")
        return []

    user_id = str(entrevista["usuario_id"])
    preguntas_finales = []

    tipos_cantidad = {
        "tecnica": entrevista.get("preguntas_tecnicas", 0),
        "blanda": entrevista.get("preguntas_blandas", 0)
    }
    print("Generando preguntas para entrevista:", entrevista_id)
    print("Tipos y cantidades:", tipos_cantidad)

    # Generar preguntas técnicas y blandas
    for tipo, cantidad in tipos_cantidad.items():
        seleccionadas = await escoger_habilidades_subtematica(db, user_id, tipo, cantidad)
        print(f"Habilidades seleccionadas para {tipo}:", seleccionadas)

        for item in seleccionadas:
            pregunta = await generar_y_guardar_pregunta(
                db=db,
                entrevista=entrevista,
                tipo=tipo,
                habilidad=item["habilidad"],
                subtematica=item["subtematica"]
            )
            if pregunta:
                preguntas_finales.append(pregunta)

    # Generar problemas de codificación si corresponde
    num_codigo = entrevista.get("preguntas_codigo", 0)
    if num_codigo > 0:
        print(f"Generando {num_codigo} problemas de codificación...")
        for _ in range(num_codigo):
            problema = await generar_problema_codigo(db, entrevista)
            if problema:
                preguntas_finales.append(problema)

    return preguntas_finales

async def generar_problema_codigo(db, entrevista: dict):
    perfil = await obtener_perfil_usuario(db, str(entrevista["usuario_id"]))
    clasificacion = perfil.get("clasificacion_junior", "desconocido")

    lenguajes = await escoger_lenguaje(db, str(entrevista["usuario_id"]), cantidad=1)
    if not lenguajes:
        print("No se pudo obtener lenguaje")
        return None

    lenguaje = lenguajes[0]

    for intento in range(5):
        problema_data = await generar_problema_codigo_llm(clasificacion, lenguaje)
        if not problema_data or "problema" not in problema_data:
            continue

        texto = problema_data["problema"]
        embedding = await vectorizar_texto(texto)
        if not embedding:
            continue

        existentes = await db["preguntas"].find({
            "tipo": "codigo",
            "usuario_id": entrevista["usuario_id"],
            "lenguaje": lenguaje
        }).to_list(200)

        if any(similitud_coseno(p["vector_embedding"], embedding) > UMBRAL_SIMILITUD for p in existentes if "vector_embedding" in p):
            continue

        doc = {
            "tipo": "codigo",
            "lenguaje": lenguaje,
            "pregunta": texto,
            "vector_embedding": embedding,
            "entrevista_id": entrevista["_id"],
            "usuario_id": entrevista["usuario_id"]
        }
        await db["preguntas"].insert_one(doc)
        return doc

    return None
