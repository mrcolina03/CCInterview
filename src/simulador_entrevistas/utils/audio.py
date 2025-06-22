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