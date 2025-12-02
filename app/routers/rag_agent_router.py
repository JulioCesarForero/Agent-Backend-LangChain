"""
Router del Agente RAG
=====================

Este módulo define el endpoint HTTP para interactuar con el Agente RAG.
Recibe peticiones POST con preguntas del usuario y retorna respuestas
generadas por el agente basadas en contexto del sistema RAG.

ENDPOINT:
- POST /ask_rag
  - Request: {"question": "texto de la pregunta"}
  - Response: {"answer": "texto de la respuesta"}

NOTA: Este archivo NO requiere modificación por parte de los estudiantes.
"""

from schemas.rag_agent_schema import QuestionRequest, AnswerResponse
from services.rag_agent_service import RAG_AGENT_SERVICE
from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter(prefix = "")


@router.post("/ask_rag", response_model = AnswerResponse)
async def ask_question(request: QuestionRequest):
    try:
        answer = await RAG_AGENT_SERVICE.ask_rag(request.question)
        # Asegurar que la respuesta se devuelva con encoding UTF-8 correcto
        return JSONResponse(
            content={"answer": answer},
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        raise e