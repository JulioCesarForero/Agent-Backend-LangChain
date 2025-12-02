"""
Schemas de Datos para el Agente RAG
====================================

Este módulo define los modelos Pydantic para validar los datos de entrada
y salida del endpoint del Agente RAG.

MODELOS:
- QuestionRequest: Valida la petición del usuario
  - question (str): La pregunta del usuario
  
- AnswerResponse: Formato de la respuesta del agente
  - answer (str): La respuesta generada por el agente

NOTA: Este archivo NO requiere modificación por parte de los estudiantes.
"""

from pydantic import BaseModel

class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    answer: str