import base64
import io
import librosa
import soundfile as sf
import numpy as np

async def procesar_audio_base64(audio_stream: io.BytesIO):
    """
    Procesa audio WAV desde un stream BytesIO
    """
    try:
        # Resetear el puntero del stream al inicio
        audio_stream.seek(0)
        
        # Cargar el audio usando librosa desde el stream
        y, sr = librosa.load(audio_stream, sr=None)
        
        # Extraer características básicas del audio
        analisis = {
            "duracion_segundos": len(y) / sr,
            "sample_rate": int(sr),
            "num_samples": len(y),
            "rms_energy": float(np.sqrt(np.mean(y**2))),
            "zero_crossing_rate": float(np.mean(librosa.feature.zero_crossing_rate(y)[0])),
            "spectral_centroid": float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)[0])),
        }
        
        # Detectar pitch/tono fundamental
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)
        
        if pitch_values:
            analisis["pitch_promedio"] = float(np.mean(pitch_values))
            analisis["pitch_std"] = float(np.std(pitch_values))
        else:
            analisis["pitch_promedio"] = 0.0
            analisis["pitch_std"] = 0.0
            
        return analisis
        
    except Exception as e:
        return {"error": f"Error en análisis de audio: {str(e)}"}
    
def evaluar_analisis_audio(analisis_audio: dict) -> dict:
    """
    Evalúa características básicas de un análisis de audio y devuelve una evaluación en lenguaje natural y una puntuación.

    Args:
        analisis_audio (dict): Diccionario con métricas de análisis de audio.

    Returns:
        dict: Contiene una evaluación textual y una puntuación numérica.
    """

    if not analisis_audio:
        return {
            "evaluacion_audio": "No se proporcionó análisis de audio.",
            "puntaje_audio": 0
        }

    duracion = analisis_audio.get("duracion_segundos", 0)
    energia = analisis_audio.get("rms_energy", 0)
    zcr = analisis_audio.get("zero_crossing_rate", 0)
    pitch_avg = analisis_audio.get("pitch_promedio", 0)
    pitch_std = analisis_audio.get("pitch_std", 0)
    centroid = analisis_audio.get("spectral_centroid", 0)

    evaluacion = []
    puntaje = 10

    # Duración
    if duracion < 2:
        evaluacion.append("La respuesta fue muy breve. Intenta extender tus respuestas para incluir más detalles y contexto.")
        puntaje -= 2
    elif duracion < 5:
        evaluacion.append("La duración fue aceptable, aunque podrías desarrollar un poco más tus ideas para lograr mayor claridad.")

    # Energía
    if energia < 0.03:
        evaluacion.append("La energía de tu voz fue baja. Trata de proyectar tu voz con más confianza y convicción.")
        puntaje -= 1
    elif energia > 0.2:
        evaluacion.append("Mostraste buena energía en tu voz, lo cual transmite entusiasmo y seguridad.")

    # Claridad vocal (ZCR)
    if zcr > 0.1:
        evaluacion.append("Se detectaron muchas transiciones rápidas en la señal. Habla un poco más pausado para mejorar la claridad.")
        puntaje -= 1
    elif zcr < 0.04:
        evaluacion.append("El ritmo fue controlado, lo cual favorece una comunicación clara.")

    # Entonación
    if pitch_avg < 80:
        evaluacion.append("La voz fue muy grave. Asegúrate de mantener un tono que facilite la comprensión.")
        puntaje -= 1
    elif pitch_avg > 300 and pitch_std > 500:
        evaluacion.append("Hubo variaciones marcadas en el tono. Intenta mantener una entonación más estable para transmitir seguridad.")
        puntaje -= 1
    else:
        evaluacion.append("La entonación fue adecuada, con variaciones naturales.")

    # Centro espectral
    if centroid < 1000:
        evaluacion.append("Tu voz podría sonar un poco apagada. Trata de vocalizar mejor para ganar presencia vocal.")
        puntaje -= 1
    elif centroid > 3000:
        evaluacion.append("La voz fue clara y con brillo, lo que ayuda a captar la atención.")

    # Asegurar que el puntaje sea al menos 0
    puntaje = max(puntaje, 0)

    return {
        "evaluacion_audio": " ".join(evaluacion),
        "puntaje_audio": puntaje
    }

