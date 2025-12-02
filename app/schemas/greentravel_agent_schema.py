"""
Schemas de Datos para el Agente GreenTravelBackend
==================================================

Este módulo define los modelos Pydantic para validar los datos de entrada
y salida del endpoint del Agente GreenTravelBackend.

MODELOS:
- QuestionRequest: Valida la petición del usuario
  - question (str): La pregunta o tarea del usuario
  
- AnswerResponse: Formato de la respuesta del agente
  - answer (str): La respuesta generada por el agente
"""

from pydantic import BaseModel, ConfigDict

class QuestionRequest(BaseModel):
    question: str
    # Configurar para ignorar campos adicionales que el frontend pueda enviar
    # (top_k, collection, use_reranking, etc.) - estos no se usan en greentravel
    model_config = ConfigDict(extra='ignore')

class AnswerResponse(BaseModel):
    answer: str

