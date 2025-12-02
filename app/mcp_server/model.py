"""
Configuración del Modelo de Lenguaje
====================================

Este módulo configura el modelo LLM (Large Language Model) que utilizarán
ambos agentes para generar respuestas.

MODELO CONFIGURADO:
- Google Gemini 2.5 Flash
- Temperature: 1.0 (creatividad alta)
- Proveedor: Google Generative AI

NOTA: Este archivo NO requiere modificación por parte de los estudiantes.
      Si desean cambiar el modelo o sus parámetros, pueden hacerlo aquí.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
import logging


logging.basicConfig(level = logging.INFO, format = "%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


logging.info("Setting model parameters")
llm = ChatGoogleGenerativeAI(model = "gemini-2.5-flash", temperature = 1.0, max_output_tokens=8192)
logging.info("Model created successfully")
