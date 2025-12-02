"""
Router del Agente GreenTravelBackend
=====================================

Este módulo define el endpoint HTTP para interactuar con el Agente GreenTravelBackend.
Recibe peticiones POST con consultas del usuario y retorna respuestas generadas
por el agente ReAct utilizando las herramientas de Liquidaciones y Proveedores.

ENDPOINT:
- POST /ask_greentravel
  - Request: {"question": "texto de la pregunta o tarea"}
  - Response: {"answer": "texto de la respuesta"}
"""

from schemas.greentravel_agent_schema import QuestionRequest, AnswerResponse
from services.custom_agent_service import CUSTOM_AGENT_SERVICE
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="")


@router.post("/ask_greentravel", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Endpoint unificado para consultas de GreenTravelBackend.
    Usa el CUSTOM_AGENT_SERVICE que ahora incluye todas las herramientas:
    - Liquidaciones (CRUD + estadísticas)
    - Proveedores (CRUD + estadísticas)
    - Facturas (obtener desde RAG + calcular vencimiento)
    """
    try:
        logger.info(f"[ASK_GREENTRAVEL] Recibida pregunta: {request.question[:100]}...")
        answer = await CUSTOM_AGENT_SERVICE.ask_custom(request.question)
        logger.info(f"[ASK_GREENTRAVEL] Respuesta generada exitosamente ({len(answer)} caracteres)")
        # Asegurar que la respuesta se devuelva con encoding UTF-8 correcto
        return JSONResponse(
            content={"answer": answer},
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"[ASK_GREENTRAVEL] Error procesando pregunta: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando la consulta: {str(e)}"
        )

