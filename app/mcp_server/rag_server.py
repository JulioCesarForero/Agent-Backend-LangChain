"""
Servidor MCP para el Agente RAG
================================

Este módulo implementa el servidor MCP que expone la herramienta para consultar
el sistema RAG externo. El agente RAG utilizará esta herramienta para recuperar
contexto relevante de la base de datos vectorial.

IMPLEMENTACIÓN SEMANA 6:
- Implementar la herramienta MCP "ask" que consulta el sistema RAG
- La herramienta debe conectarse a la API del RAG (desarrollado en semanas anteriores)
- Debe manejar errores de conexión y timeout
- Retornar el contexto recuperado como string
"""

from mcp.server.fastmcp import FastMCP
import logging
import httpx
import os
import sys


# Configurar logging con UTF-8
# IMPORTANTE: Usar sys.stderr en lugar de sys.stdout para no interferir con MCP stdio
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr)  # stderr para no interferir con MCP stdio
    ]
)
# Asegurar que el handler use UTF-8
for handler in logging.root.handlers:
    if hasattr(handler, 'stream') and hasattr(handler.stream, 'reconfigure'):
        try:
            handler.stream.reconfigure(encoding='utf-8')
        except:
            pass

logger = logging.getLogger(__name__)

mcp = FastMCP("rag-server")


# ===============================================================================
# SEMANA 6: Implementar el servidor MCP para RAG
# ===============================================================================

# Configuración del RAG
rag_collection = "semana3_test_collection"
rag_top_k = 5
rag_use_reranking = True
rag_use_query_rewriting = True


@mcp.tool()
async def ask(query: str) -> str:
    """
    Consulta el sistema RAG externo para recuperar contexto relevante.
    
    Esta herramienta se conecta al backend RAG y realiza una consulta para
    obtener información relevante basada en la pregunta del usuario.
    
    Args:
        query (str): La pregunta del usuario que se enviará al sistema RAG
    
    Returns:
        str: El contexto recuperado del RAG (campo 'answer' de la respuesta)
    
    Raises:
        ValueError: Si RAG_BASE_URL no está configurado
        httpx.HTTPError: Si hay un error en la conexión HTTP
        httpx.TimeoutException: Si la petición excede el timeout
    """
    # Obtener la URL base del RAG desde variables de entorno o usar valor por defecto
    rag_base_url = os.getenv("RAG_BASE_URL", "http://34.63.203.124")
    if not rag_base_url:
        error_msg = "RAG_BASE_URL no está configurado en las variables de entorno"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Construir la URL completa del endpoint
    # El endpoint del RAG es /api/v1/ask según la documentación
    rag_url = f"{rag_base_url.rstrip('/')}/api/v1/ask"
    
    # Preparar el payload de la petición
    payload = {
        "question": query,
        "top_k": rag_top_k,
        "collection": rag_collection,
        "use_reranking": rag_use_reranking,
        "use_query_rewriting": rag_use_query_rewriting
    }
    
    logger.info(f"Consultando RAG en {rag_url} con pregunta: {query[:50]}...")
    
    try:
        # Realizar la petición POST al sistema RAG
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(rag_url, json=payload)
            response.raise_for_status()
            
            # Extraer la respuesta JSON
            result = response.json()
            
            # Extraer el campo 'answer' de la respuesta
            if "answer" not in result:
                error_msg = f"La respuesta del RAG no contiene el campo 'answer'. Respuesta: {result}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            answer = result["answer"]
            logger.info(f"Respuesta del RAG recuperada exitosamente ({len(answer)} caracteres)")
            return answer
            
    except httpx.TimeoutException as e:
        error_msg = f"Timeout al consultar el sistema RAG: {str(e)}"
        logger.error(error_msg)
        raise httpx.TimeoutException(error_msg) from e
    except httpx.HTTPError as e:
        error_msg = f"Error HTTP al consultar el sistema RAG: {str(e)}"
        logger.error(error_msg)
        raise httpx.HTTPError(error_msg) from e
    except Exception as e:
        error_msg = f"Error inesperado al consultar el sistema RAG: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


if __name__ == "__main__":
    mcp.run(transport="stdio")