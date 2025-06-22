import os
import json
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generar_perfil_usuario(cv_dict):
    prompt = f"""
Eres un asistente de RRHH especializado en perfiles de desarrollo de software junior.

No escribas fuera del JSON.

A partir del siguiente CV en formato JSON, genera un perfil resumido con los siguientes campos:

1. clasificacion_junior: selecciona solo una de las siguientes categorías predefinidas. Responde solo con el nombre de la categoría:
- "junior_academico": estudiante o egresado reciente de carrera universitaria sin experiencia práctica o con proyectos académicos.
- "junior_con_practicas": ha realizado prácticas profesionales o trabajos breves en la industria.
- "junior_autodidacta": ha aprendido de forma independiente y tiene proyectos personales o repositorios en GitHub.
- "junior_bootcamp": se ha formado en programas intensivos tipo bootcamp con proyectos prácticos.
- "junior_tecnico": egresado de formación técnica orientada a la práctica.
- "junior_mixto": combinación de al menos dos vías anteriores (ej. universidad + bootcamp).

2. tematicas_a_evaluar: lista de objetos, cada uno representando una habilidad técnica o blanda. Cada objeto contiene:
  - "habilidad": nombre de la habilidad
  - "tipo": "tecnica" o "blanda"
  - "nivel_esperado": "básico", "intermedio" o "avanzado"
  - "subtematicas": lista de subtemas (5 si es habilidad técnica y 3 si es blanda) con:
    - "nombre": nombre del subtema
    - "puntuacion": valor inicial siempre 0

Para habilidades blandas, usa exactamente estas 8:
- Comunicación efectiva
- Trabajo en equipo
- Adaptabilidad
- Gestión del tiempo
- Recepción de feedback
- Responsabilidad
- Pensamiento crítico
- Proactividad

Las habilidades técnicas se deducen del CV, mientras que las blandas se definen de las enviadas. No omitas habilidades técnicas relevantes del CV.
No omitas habilidades blandas, incluye todas las 8 mencionadas.

Ejemplo de salida:
{{
  "clasificacion_junior": "junior_con_practicas",
  "tematicas_a_evaluar": [
    {{
      "habilidad": "Python",
      "tipo": "tecnica",
      "nivel_esperado": "intermedio",
      "subtematicas": [
        {{"nombre": "Sintaxis básica", "puntuacion": 0}},
        {{"nombre": "Estructuras de control", "puntuacion": 0}},
        {{"nombre": "POO", "puntuacion": 0}},
        {{"nombre": "Manejo de errores", "puntuacion": 0}},
        {{"nombre": "Manipulación de datos", "puntuacion": 0}}
      ]
    }},
    ... Todas las habilidades técnicas que correspondan al CV,
    {{
      "habilidad": "Comunicación efectiva",
      "tipo": "blanda",
      "nivel_esperado": "básico",
      "subtematicas": [
        {{"nombre": "Escucha activa", "puntuacion": 0}},
        {{"nombre": "Claridad al hablar", "puntuacion": 0}},
        {{"nombre": "Comunicación escrita", "puntuacion": 0}},
      ]
      ... Todas las habilidades blandas mencionadas anteriormente
    }}
  ]
}}


CV:

{cv_dict}
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        contenido = response.choices[0].message.content.strip()
        perfil = json.loads(contenido)
        return perfil

    except json.JSONDecodeError as e:
        logging.error(f"Error al parsear el JSON del modelo: {e}")
    except Exception as e:
        logging.error(f"Error inesperado al generar el perfil: {e}")

    return None

async def generar_habilidad_con_subtematicas(habilidades_actuales, clasificacion: str, tipo: str):
    prompt = f"""
Eres un sistema que apoya la evaluación de habilidades en programadores junior. Dado el siguiente conjunto de habilidades técnicas actuales que dice tener el usuario:

{habilidades_actuales}

Y la clasificación del usuario como: '{clasificacion}'

SUGIERE una nueva **habilidad {tipo}** que:
- No repita tecnologías ya listadas.
- Sea coherente y complementaria con las habilidades ya existentes.
- Enfoque en **habilidades fundamentales**, ya que no se puede asumir habilidades específicas que no mencionó el usuario.
- Evita introducir tecnologías avanzadas, específicas o disonantes (por ejemplo, no sugerir lenguajes que el usuario no especifica en sus habilidades).
- Evita que sean subtemáticas directas de alguna de las habilidades. 

Ejemplo de razonamiento correcto:

Si el usuario indica que conoce: ["Java", "C#", "SQL Server", "Git", "Docker", "Metodologías ágiles", "DevOps"]; No se debe sugerir una tecnología completamente distinta como Python. Sin embargo, sí es válido sugerir algo fundamental y transversal, como: Bash / Línea de comandos básica"

Justificación: El uso de Docker y DevOps implica que probablemente el usuario interactúa con entornos de línea de comandos. Aunque no lo haya declarado, es razonable suponer un conocimiento o necesidad básica de terminal, especialmente en roles técnicos junior.

Tu tarea: Sugiere una nueva habilidad siguiendo esa lógica y genera 5 subtemáticas relevantes para evaluarla, relacionadas con sus fundamentos.

Devuelve el resultado como JSON en el siguiente formato:

{{
  "habilidad": "nombre de la habilidad",
  "subtematicas": [
    {{"nombre": "Subtema 1", "puntuacion": 0}},
    {{"nombre": "Subtema 2", "puntuacion": 0}},
    {{"nombre": "Subtema 3", "puntuacion": 0}},
    {{"nombre": "Subtema 4", "puntuacion": 0}},
    {{"nombre": "Subtema 5", "puntuacion": 0}}
  ]
}}
    """.strip()

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        contenido = response.choices[0].message.content.strip()
        data = json.loads(contenido)
        return {
            "habilidad": data["habilidad"],
            "tipo": tipo,
            "nivel_esperado": "basico",
            "subtematicas": data.get("subtematicas", [])
        }
    except Exception as e:
        logging.error(f"Error al generar habilidad con subtemáticas: {e}")
        return None
      
async def generar_subtematica_llm(habilidad: str, tipo: str, nivel: str, subtematicas_actuales: list[str]):
    prompt = f"""
Actúas como generador de contenido educativo para entrevistas técnicas.

Dada la habilidad '{habilidad}' (tipo: {tipo}, nivel: {nivel}) y las subtemáticas ya existentes:

{subtematicas_actuales}

Sugiere una **nueva subtemática relevante y original**, que **no se repita** y **apoye la comprensión integral de la habilidad**. Devuélvela en JSON como:

{{"nombre": "nombre de la subtemática"}}
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        contenido = response.choices[0].message.content.strip()
        return json.loads(contenido)
    except Exception as e:
        logging.error(f"Error al generar subtemática desde LLM: {e}")
        return None

async def generar_pregunta_llm(clasificacion: str, tipo: str, habilidad: str, nivel: str, subtematica: str):
    if tipo == "tecnica":
        prompt = f"""
Eres un sistema experto en entrevistas técnicas para programadores junior.

El usuario está clasificado como: {clasificacion}
Habilidad a evaluar: {habilidad}
Nivel esperado: {nivel}
Subtemática específica: {subtematica}

Genera una pregunta técnica **clara, específica y coherente con el nivel esperado**, evitando jergas complejas. La pregunta debe ser lo suficientemente concreta como para ser respondida en entrevista oral.

Devuelve solo la pregunta, sin explicación ni justificación.
        """.strip()
    elif tipo == "blanda":
        prompt = f"""
Eres un sistema experto en entrevistas de habilidades blandas para programadores junior.

El usuario está clasificado como: {clasificacion}
Habilidad blanda a evaluar: {habilidad}
Subtemática específica: {subtematica}

Genera una pregunta de entrevista que evalúe esa habilidad blanda, coherente con un perfil junior. Sé directo, no uses lenguaje técnico.

Devuelve solo la pregunta, sin explicación.
        """.strip()
    else:
        return None  # o lanzar error si se desea

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error al generar pregunta: {e}")
        return None

async def identificar_lenguajes_judge0(tecnicas: list) -> list:
    prompt = f"""
Dado este conjunto de habilidades técnicas:

{[h['habilidad'] for h in tecnicas]}

Selecciona únicamente aquellas que correspondan a **lenguajes de programación compatibles con Judge0**, ignorando herramientas, frameworks, librerías o conceptos generales.

Devuelve una lista en formato JSON como:
["Python", "C", "C++"]
    """.strip()

    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logging.error(f"Error al identificar lenguajes: {e}")
        return []

async def generar_problema_codigo_llm(clasificacion: str, lenguaje: str):
    prompt = f"""
Eres un sistema experto en entrevistas de programación para perfiles junior.

El usuario está clasificado como: {clasificacion}
Lenguaje a evaluar: {lenguaje}

Genera un problema de programación práctico, claro y sencillo, que pueda resolverse en menos de 10 minutos, del estilo de entrevista técnica.

El problema debe poder ejecutarse directamente, y el usuario deberá imprimir en consola el resultado con la función correspondiente (por ejemplo, `print()` en Python).

Devuelve un JSON con el siguiente formato:

{{
  "problema": "Enunciado claro del problema"
}}

Evita explicaciones adicionales, solo el JSON.
""".strip()

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logging.error(f"Error al generar problema de código: {e}")
        return None

async def evaluar_respuesta_llm(pregunta: str, respuesta_usuario: str) -> dict:
    """
    Evalúa la calidad de una respuesta a una pregunta de entrevista.
    Devuelve un dict con feedback, puntuación y sugerencias.
    """
    prompt = f"""
Eres un evaluador de entrevistas técnicas y blandas para desarrolladores junior.

Pregunta de entrevista:
"{pregunta}"

Respuesta del candidato:
"{respuesta_usuario}"

Evalúa de forma objetiva la respuesta. Devuelve solo un JSON con los siguientes campos:
- "puntaje": número entero entre 0 y 10 (0 = muy mala, 10 = excelente)
- "justificacion": texto explicando por qué se asignó ese puntaje
- "sugerencias": texto con recomendaciones claras y breves para mejorar esa respuesta

Formato de respuesta:
{{
  "puntaje": 8,
  "justificacion": "La respuesta demuestra conocimiento técnico adecuado y ejemplos concretos.",
  "sugerencias": "Podrías ser más preciso con términos técnicos y evitar rodeos."
}}
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",  # puedes usar "gpt-3.5-turbo" si prefieres
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        resultado = json.loads(response.choices[0].message.content.strip())
        return resultado
    except Exception as e:
        logging.error(f"Error al evaluar respuesta del usuario: {e}")
        return {
            "puntaje": 0,
            "justificacion": "No se pudo evaluar la respuesta.",
            "sugerencias": "Intenta responder de nuevo con mayor claridad."
        }

async def evaluar_codigo_llm(problema: str, codigo_usuario: str, salida: str | None, error: str | None, estado: str) -> dict:
    prompt = f"""
Eres un experto evaluador técnico en entrevistas de programación para perfiles junior.

A continuación se presenta un problema de código, la solución propuesta por el usuario y el resultado de la ejecución:

---
Problema:
{problema}

Código del usuario:
{codigo_usuario}

Estado de compilación: {estado}
Salida estándar:
{salida or 'N/A'}
Errores de compilación o ejecución:
{error or 'Ninguno'}
---

Evalúa la solución del usuario en una escala del 1 al 10.
Considera:
- Correctitud del resultado
- Buenas prácticas y legibilidad
- Manejo de errores y validación
- Estilo de codificación (estructuración, claridad)

Devuelve un JSON con los siguientes campos:
{{
  "puntuacion": valor entero entre 0 y 10,
  "justificacion": "breve justificación de por qué se le dio esa puntuación",
  "recomendaciones": "sugerencias de mejora para que el usuario pueda mejorar su solución"
}}

No añadas ninguna explicación adicional fuera del JSON.
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logging.error(f"Error al evaluar codigo con LLM: {e}")
        return None

async def generar_boilerplate_lenguaje(nombre_lenguaje: str) -> str:
    prompt = f"""
    Eres un asistente que ayuda a generar plantillas mínimas de código listas para ejecutarse en Judge0.
    Devuelve únicamente el código necesario en el lenguaje {nombre_lenguaje} para que se pueda compilar sin errores.
    No incluyas explicaciones. Deja comentarios para indicar dónde el usuario puede escribir su lógica.
    El resultado debe estar en formato plano compatible con el editor Monaco.
    No añadas encabezados, ni backticks, ni comillas, etc.
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un experto en compilación y compatibilidad de código."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error al generar boilerplate para {nombre_lenguaje}: {e}")
        return ""
