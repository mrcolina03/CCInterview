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
        return {"evaluacion_audio": "No se proporcionó análisis de audio.", "puntaje_audio": 0}

    duracion = analisis_audio.get("duracion_segundos", 0)
    energia = analisis_audio.get("rms_energy", 0)
    zcr = analisis_audio.get("zero_crossing_rate", 0)
    pitch_avg = analisis_audio.get("pitch_promedio", 0)
    pitch_std = analisis_audio.get("pitch_std", 0)
    centroid = analisis_audio.get("spectral_centroid", 0)

    evaluacion = []
    puntaje = 10

    # Duración muy corta podría indicar una respuesta incompleta
    if duracion < 2:
        evaluacion.append("La respuesta fue muy corta, posiblemente incompleta.")
        puntaje -= 2

    # Energía de la voz
    if energia < 0.03:
        evaluacion.append("La energía de la voz fue baja, lo que puede indicar falta de confianza.")
        puntaje -= 1
    elif energia > 0.2:
        evaluacion.append("La energía fue elevada, lo cual puede reflejar entusiasmo.")

    # Claridad vocal (Zero Crossing Rate)
    if zcr > 0.1:
        evaluacion.append("La señal presenta muchas transiciones, podría haber ruido o hablar rápido.")
        puntaje -= 1

    # Entonación
    if pitch_avg < 80:
        evaluacion.append("La voz fue muy grave, lo cual podría dificultar la comprensión.")
        puntaje -= 1
    elif pitch_avg > 300 and pitch_std > 500:
        evaluacion.append("La voz tuvo variaciones de tono muy marcadas, posiblemente falta de control vocal.")
        puntaje -= 1

    # Espectro
    if centroid < 1000:
        evaluacion.append("El centro espectral fue bajo, la voz puede sonar apagada.")
        puntaje -= 1
    elif centroid > 3000:
        evaluacion.append("El centro espectral fue alto, lo que sugiere una voz brillante o aguda.")

    if puntaje < 0:
        puntaje = 0

    return {
        "evaluacion_audio": " ".join(evaluacion) if evaluacion else "La calidad vocal fue adecuada.",
        "puntaje_audio": puntaje
    }
