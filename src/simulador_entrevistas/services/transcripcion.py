import openai
from openai import OpenAI
import tempfile
import os
import time

client = OpenAI()

async def transcribir_audio(audio_bytes: bytes) -> str:
    """
    Transcribe audio usando Whisper de OpenAI
    """
    temp_file_path = None
    try:
        # Crear archivo temporal con extensión .wav
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            temp_file_path = tmp.name
            tmp.write(audio_bytes)
            tmp.flush()
        
        # Abrir el archivo para transcripción (fuera del context manager)
        with open(temp_file_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="es"  # Especificamos español para mejor precisión
            )
        if(transcription.text == "Subtítulos realizados por la comunidad de Amara.org"):
            transcription.text = "No respondio"
        return transcription.text
        
    except Exception as e:
        print(f"Error en transcripción: {e}")
        return f"Error en transcripción: {str(e)}"
    
    finally:
        # Limpiar archivo temporal de forma segura
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                # Pequeña pausa para asegurar que el archivo se libere
                time.sleep(0.1)
                os.unlink(temp_file_path)
            except PermissionError:
                # Si no se puede eliminar inmediatamente, programar para más tarde
                try:
                    time.sleep(0.5)
                    os.unlink(temp_file_path)
                except:
                    print(f"No se pudo eliminar archivo temporal: {temp_file_path}")
                    pass
