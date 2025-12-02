"""
Aplicación Principal - Backend de Agentes Inteligentes
=======================================================

Este es el punto de entrada principal de la aplicación FastAPI que orquesta
los agentes inteligentes: RAG Agent, Custom Agent y GreenTravelBackend Agent.

CONFIGURACIÓN:
- CORS habilitado para localhost:3000 (frontend)
- Servidores MCP configurados para todos los agentes
- UTF-8 encoding para manejo correcto de caracteres especiales
"""

from services.custom_agent_service import CUSTOM_AGENT_SERVICE
from services.rag_agent_service import RAG_AGENT_SERVICE
from services.greentravel_agent_service import GREEN_TRAVEL_AGENT_SERVICE
from routers import rag_agent_router, custom_agent_router, greentravel_agent_router
from mcp_server.config import get_server_parameters, get_greentravel_server_parameters
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title = "202515 MISW4411 Agent Backend Template")


# Configurar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend local
        "http://127.0.0.1:3000",   # Alternativa localhost
        "http://136.115.143.51/",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)


app.include_router(rag_agent_router.router)
app.include_router(custom_agent_router.router)
app.include_router(greentravel_agent_router.router)


@app.get("/health")
async def health_check():
    """Endpoint de health check para verificar que el backend está funcionando."""
    return {"status": "ok", "message": "Backend is running"}


rag_agent_parameters = get_server_parameters("/app/mcp_server/rag_server.py")
RAG_AGENT_SERVICE.set_server_parameters(rag_agent_parameters)


custom_agent_parameters = get_server_parameters("/app/mcp_server/custom_server.py")
CUSTOM_AGENT_SERVICE.set_server_parameters(custom_agent_parameters)


greentravel_agent_parameters = get_greentravel_server_parameters()
GREEN_TRAVEL_AGENT_SERVICE.set_server_parameters(greentravel_agent_parameters)
