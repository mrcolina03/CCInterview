
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Literal
from bson import ObjectId
from fastapi import HTTPException
from openai import AsyncOpenAI
from services.llm import generar_habilidad_con_subtematicas, generar_subtematica_llm, identificar_lenguajes_judge0

# Creación de habilidades y subtemáticas adaptativas en función de criterios de adaptación

async def obtener_config(db: AsyncIOMotorDatabase):
    return await db["config"].find_one({"_id": "criterios_adaptacion"})

async def obtener_perfil_usuario(db: AsyncIOMotorDatabase, usuario_id: str):
    try:
        object_id = ObjectId(usuario_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")

    return await db["perfil_usuario"].find_one({"usuario_id": object_id})

async def contar_preguntas_por_subtematica(db: AsyncIOMotorDatabase, usuario_id: str, habilidad: str, subtematica: str):
    return await db["preguntas"].count_documents({
        "usuario_id": usuario_id,
        "habilidad": habilidad,
        "subtematica": subtematica
    })

async def evaluar_creacion_nueva_habilidad(db: AsyncIOMotorDatabase, usuario_id: str, tipo: Literal["tecnica", "blanda"]):
    config = await obtener_config(db)
    perfil = await obtener_perfil_usuario(db, usuario_id)
    if not config or not perfil:
        print("No se pudo obtener la configuración o el perfil del usuario.")
        return False

    habilidades_config = config.get("habilidades", {})
    habilidades = [h for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == tipo]

    if not habilidades:
        return True

    total = len(habilidades)
    condiciones_cumplidas = 0

    for clave, criterio in habilidades_config.items():
        if not criterio.get("activo", False):
            continue
        valor = criterio.get("valor")
        porcentaje = criterio.get("porcentaje", 1.0)

        if clave == "umbral_dominio_global":
            cumplidas = 0
            for h in habilidades:
                subs = h.get("subtematicas", [])
                if subs:
                    promedio = sum(s["puntuacion"] for s in subs) / len(subs)
                    if promedio >= valor:
                        cumplidas += 1
            if cumplidas / total >= porcentaje:
                condiciones_cumplidas += 1

        elif clave == "num_subtematicas":
            cumplidas = sum(1 for h in habilidades if len(h.get("subtematicas", [])) >= valor)
            if cumplidas / total >= porcentaje:
                condiciones_cumplidas += 1

    return condiciones_cumplidas > 0

async def evaluar_creacion_nueva_subtematica(db: AsyncIOMotorDatabase, usuario_id: str, tipo: Literal["tecnica", "blanda"]):
    config = await obtener_config(db)
    perfil = await obtener_perfil_usuario(db, usuario_id)
    if not config or not perfil:
        return {}

    sub_config = config.get("subtematicas", {})
    habilidades = [h for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == tipo]
    resultado = {}

    for h in habilidades:
        nombre = h["habilidad"]
        subs = h.get("subtematicas", [])
        if not subs:
            continue

        total = len(subs)
        dominio_ok = 0
        preguntas_ok = 0

        for sub in subs:
            if sub["puntuacion"] >= sub_config.get("umbral_dominio", {}).get("valor", 10):
                dominio_ok += 1
            conteo = await contar_preguntas_por_subtematica(db, usuario_id, nombre, sub["nombre"])
            if conteo >= sub_config.get("num_preguntas", {}).get("valor", 10):
                preguntas_ok += 1

        criterio_dominio = sub_config.get("umbral_dominio", {})
        criterio_preguntas = sub_config.get("num_preguntas", {})

        cumple_dominio = criterio_dominio.get("activo", False) and dominio_ok / total >= criterio_dominio.get("porcentaje", 1.0)
        cumple_preguntas = criterio_preguntas.get("activo", False) and preguntas_ok / total >= criterio_preguntas.get("porcentaje", 1.0)

        resultado[nombre] = cumple_dominio or cumple_preguntas

    return resultado

async def generar_nueva_habilidad(db: AsyncIOMotorDatabase, usuario_id: str, tipo: Literal["tecnica", "blanda"]):
    perfil = await obtener_perfil_usuario(db, usuario_id)
    habilidades_actuales = [h["habilidad"] for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == tipo]
    clasificacion = perfil.get("clasificacion_junior", "desconocido")

    print(f"clasificacion: {clasificacion}")
    print(f"habilidades_actuales: {habilidades_actuales}")

    habilidad_nueva = await generar_habilidad_con_subtematicas(habilidades_actuales, clasificacion, tipo)
    if not habilidad_nueva:
        return None

    # Calcular el índice mínimo global para ese tipo (para sincronizar el ciclo)
    habilidades_tipo = [h for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == tipo]
    min_indice_habilidad = min((h.get("indice_uso", 0) for h in habilidades_tipo), default=0)

    subtematicas = habilidad_nueva.get("subtematicas", [])
    min_indice_sub = min(
        (sub.get("indice_uso", 0)
         for h in habilidades_tipo
         for sub in h.get("subtematicas", [])),
        default=0
    )

    # Aplicar los índices sincronizados
    for sub in subtematicas:
        sub.setdefault("puntuacion", 0)
        sub["indice_uso"] = min_indice_sub
        sub["reforzar"] = False

    habilidad_nueva["indice_uso"] = min_indice_habilidad
    habilidad_nueva["tipo"] = tipo

    await db["perfil_usuario"].update_one(
        {"usuario_id": ObjectId(usuario_id)},
        {"$push": {"tematicas_a_evaluar": habilidad_nueva}}
    )

    return habilidad_nueva

async def generar_nueva_subtematica(db: AsyncIOMotorDatabase, usuario_id: str, habilidad: str, tipo: str):
    perfil = await obtener_perfil_usuario(db, usuario_id)

    habilidad_data = next(
        (h for h in perfil.get("tematicas_a_evaluar", []) if h["habilidad"] == habilidad and h["tipo"] == tipo),
        None
    )
    if not habilidad_data:
        return None

    subtematicas_actuales = habilidad_data.get("subtematicas", [])
    subtematicas_nombres = [s["nombre"] for s in subtematicas_actuales]
    nivel = habilidad_data.get("nivel_esperado", "basico")

    sub = await generar_subtematica_llm(habilidad, tipo, nivel, subtematicas_nombres)
    if not sub or "nombre" not in sub:
        return None

    # Buscar el índice de uso mínimo de las subtemáticas actuales para mantener el ciclo
    min_indice_sub = min((s.get("indice_uso", 0) for s in subtematicas_actuales), default=0)

    nueva_sub = {
        "nombre": sub["nombre"],
        "puntuacion": 0,
        "indice_uso": min_indice_sub,
        "reforzar": False
    }

    await db["perfil_usuario"].update_one(
        {"usuario_id": ObjectId(usuario_id), "tematicas_a_evaluar.habilidad": habilidad},
        {"$push": {"tematicas_a_evaluar.$.subtematicas": nueva_sub}}
    )

    return nueva_sub

# Seleccionar habilidades y subtemáticas de forma adaptativa

def mezclar_tematicas(originales: list, modificadas: list, tipo: str) -> list:
    actualizadas = []
    for h in originales:
        if h["tipo"] != tipo:
            actualizadas.append(h)
        else:
            encontrada = next((m for m in modificadas if m["habilidad"] == h["habilidad"]), None)
            actualizadas.append(encontrada if encontrada else h)
    return actualizadas

async def actualizar_indices_y_refuerzo(db, usuario_id: str, tipo: Literal["tecnica", "blanda"]):
    perfil = await obtener_perfil_usuario(db, usuario_id)
    if not perfil:
        return

    for habilidad in perfil.get("tematicas_a_evaluar", []):
        if habilidad["tipo"] != tipo:
            continue

        habilidad.setdefault("indice_uso", 0)
        for sub in habilidad.get("subtematicas", []):
            sub.setdefault("indice_uso", 0)
            sub.setdefault("reforzar", False)

    await db["perfil_usuario"].update_one(
        {"usuario_id": perfil["usuario_id"]},
        {"$set": {"tematicas_a_evaluar": perfil["tematicas_a_evaluar"]}}
    )

async def activar_refuerzo_si_corresponde(db, usuario_id: str, tipo: Literal["tecnica", "blanda"]):
    config = await obtener_config(db)
    if not config or not config.get("subtematicas", {}).get("refuerzo_repeticion", {}).get("activo", False):
        return

    porcentaje = config["subtematicas"]["refuerzo_repeticion"].get("porcentaje", 0.1)
    perfil = await obtener_perfil_usuario(db, usuario_id)
    if not perfil:
        return

    tematicas = [h for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == tipo]

    for habilidad in tematicas:
        subtematicas = habilidad.get("subtematicas", [])
        if not subtematicas:
            continue

        # Marcar las subtematicas con menor puntuación para refuerzo
        subtematicas.sort(key=lambda s: s["puntuacion"])
        n = max(1, round(len(subtematicas) * porcentaje))
        for sub in subtematicas[:n]:
            sub["reforzar"] = True

    perfil.setdefault("estado_refuerzo", {})[tipo] = "activo"
    tematicas_final = mezclar_tematicas(perfil["tematicas_a_evaluar"], tematicas, tipo)
    await db["perfil_usuario"].update_one(
        {"usuario_id": perfil["usuario_id"]},
        {"$set": {
            "tematicas_a_evaluar": tematicas_final,
            "estado_refuerzo": perfil["estado_refuerzo"]
        }}
    )

def verificar_ciclo_completo(tematicas: list) -> bool:
    """
    Verifica si se completó un ciclo completo comparando el mínimo y máximo índice de uso
    de todas las subtematicas. Un ciclo está completo cuando todas las subtematicas
    han sido evaluadas al menos una vez más que el mínimo actual.
    """
    todos_los_indices = []
    for habilidad in tematicas:
        for sub in habilidad.get("subtematicas", []):
            todos_los_indices.append(sub.get("indice_uso", 0))
    
    if not todos_los_indices:
        return False
    
    min_uso = min(todos_los_indices)
    max_uso = max(todos_los_indices)
    
    # Ciclo completo cuando la diferencia entre max y min es >= 1
    # y todas las subtematicas han sido usadas al menos una vez
    return max_uso > min_uso and min_uso > 0

async def escoger_habilidades_subtematica(db, usuario_id: str, tipo: Literal["tecnica", "blanda"], cantidad: int):
    await actualizar_indices_y_refuerzo(db, usuario_id, tipo)
    perfil = await obtener_perfil_usuario(db, usuario_id)
    if not perfil:
        return []

    estado_refuerzo = perfil.get("estado_refuerzo", {}).get(tipo, "inactivo")

    tematicas = [h for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == tipo]
    if not tematicas:
        return []

    seleccionadas = []

    while len(seleccionadas) < cantidad:
        # Verificar si es momento de activar refuerzo
        ciclo_completo = all(
            len(set(sub.get("indice_uso", 0) for sub in h.get("subtematicas", []))) == 1
            for h in tematicas
        )

        if ciclo_completo and estado_refuerzo == "inactivo":
            print("🔁 Ciclo completo detectado. Activando refuerzo...")
            await activar_refuerzo_si_corresponde(db, usuario_id, tipo)
            perfil = await obtener_perfil_usuario(db, usuario_id)
            estado_refuerzo = "activo"
            tematicas = [h for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == tipo]
        elif not any(any(sub.get("reforzar", False) for sub in h.get("subtematicas", [])) for h in tematicas):
            estado_refuerzo = "inactivo"

        print(f"🚦 Modo actual: {'REFUERZO' if estado_refuerzo == 'activo' else 'NORMAL'}")

        for habilidad in tematicas:
            subtematicas = habilidad.get("subtematicas", [])
            if not subtematicas:
                continue

            if estado_refuerzo == "activo":
                reforzando = [s for s in subtematicas if s.get("reforzar", False)]
                if reforzando:
                    sub = sorted(reforzando, key=lambda s: s["puntuacion"])[0]
                    sub["reforzar"] = False
                    print(f"📌 Refuerzo: {sub['nombre']} (p: {sub['puntuacion']})")
                else:
                    # Si no hay más para reforzar, continuar con normalidad
                    sub = min(subtematicas, key=lambda s: s.get("indice_uso", 0))
                    sub["indice_uso"] += 1
                    print(f"✅ Normal: {sub['nombre']} (uso: {sub['indice_uso']})")
            else:
                sub = min(subtematicas, key=lambda s: s.get("indice_uso", 0))
                sub["indice_uso"] += 1
                print(f"✅ Normal: {sub['nombre']} (uso: {sub['indice_uso']})")

            habilidad["indice_uso"] = sum(s["indice_uso"] for s in subtematicas)
            seleccionadas.append({
                "habilidad": habilidad["habilidad"],
                "subtematica": sub["nombre"]
            })

            if len(seleccionadas) >= cantidad:
                break

    # Actualizar estado final
    perfil.setdefault("estado_refuerzo", {})[tipo] = estado_refuerzo
    tematicas_final = mezclar_tematicas(perfil["tematicas_a_evaluar"], tematicas, tipo)

    await db["perfil_usuario"].update_one(
        {"usuario_id": perfil["usuario_id"]},
        {"$set": {
            "tematicas_a_evaluar": tematicas_final,
            "estado_refuerzo": perfil["estado_refuerzo"]
        }}
    )

    return seleccionadas

async def detectar_lenguajes_perfil(db: AsyncIOMotorDatabase, usuario_id: str):
    perfil = await obtener_perfil_usuario(db, usuario_id)
    print(f"perfil: {perfil}")
    if not perfil:
        print(f"No se encontró el perfil")
        return

    tecnicas = [h for h in perfil.get("tematicas_a_evaluar", []) if h["tipo"] == "tecnica"]
    print(f"tecnicas extraidas: {tecnicas}")
    lenguajes = await identificar_lenguajes_judge0(tecnicas)
    print(f"lenguajes generados por modelo: {lenguajes}")

    if not lenguajes:
        print(f"No se encontró lenguajes creados por el modelo")
        return

    existentes = perfil.get("lenguajes_evaluar", [])
    nuevos = [{"lenguaje": l, "indice_uso": 0} for l in lenguajes if l not in [e["lenguaje"] for e in existentes]]

    if nuevos:
        await db["perfil_usuario"].update_one(
            {"usuario_id": perfil["usuario_id"]},
            {"$push": {"lenguajes_evaluar": {"$each": nuevos}}}
        )

async def escoger_lenguaje(db: AsyncIOMotorDatabase, usuario_id: str, cantidad: int):
    perfil = await obtener_perfil_usuario(db, usuario_id)
    lenguajes = perfil.get("lenguajes_evaluar", [])

    if not lenguajes:
        return []

    # Ordenar por índice de uso
    ordenados = sorted(lenguajes, key=lambda l: l.get("indice_uso", 0))
    seleccion = ordenados[:cantidad]

    # Actualizar índice de uso en memoria
    for lang in seleccion:
        lang["indice_uso"] += 1

    await db["perfil_usuario"].update_one(
        {"usuario_id": perfil["usuario_id"]},
        {"$set": {"lenguajes_evaluar": lenguajes}}
    )

    return [l["lenguaje"] for l in seleccion]

