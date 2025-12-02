"""
Cargador de Herramientas MCP
=============================

Este módulo es responsable de cargar las herramientas definidas en los
servidores MCP y convertirlas en objetos utilizables por LangChain.

RESPONSABILIDADES:
- Conectarse a la sesión MCP activa
- Cargar todas las herramientas expuestas por el servidor MCP
- Convertir herramientas MCP a formato LangChain
- Crear diccionario de herramientas indexadas por nombre

NOTA: Este archivo NO requiere modificación por parte de los estudiantes.
"""

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession
import logging


logging.basicConfig(level = logging.INFO, format = "%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def load_tools(session: ClientSession):
    tools = await load_mcp_tools(session)
    logging.info("Tools loaded successfully")
    tools_by_name = {tool.name: tool for tool in tools}
    logging.info("Tools by name loaded successfully")
    return tools, tools_by_name