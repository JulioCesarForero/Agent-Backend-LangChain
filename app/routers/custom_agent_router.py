"""
Router del Agente Especializado
================================

Este módulo define el endpoint HTTP para interactuar con el Agente Especializado.
Recibe peticiones POST con tareas del usuario y retorna respuestas generadas
por el agente ReAct utilizando las herramientas especializadas disponibles.

ENDPOINT:
- POST /ask_custom
  - Request: {"question": "texto de la pregunta o tarea"}
  - Response: {"answer": "texto de la respuesta"}

NOTA: Este archivo NO requiere modificación por parte de los estudiantes.
"""

from schemas.custom_agent_schema import QuestionRequest, AnswerResponse
from services.custom_agent_service import CUSTOM_AGENT_SERVICE
from fastapi import APIRouter


router = APIRouter(prefix = "")


@router.post("/ask_custom", response_model = AnswerResponse)
async def ask_question(request: QuestionRequest):
    try:
        answer = await CUSTOM_AGENT_SERVICE.ask_custom(request.question)
    except Exception as e:
        raise e
    return {"answer": answer}