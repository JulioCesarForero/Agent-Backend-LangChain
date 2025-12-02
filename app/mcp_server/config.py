"""
Configuración de Servidores MCP
================================

Este módulo configura los parámetros necesarios para ejecutar los servidores
MCP (Model Context Protocol) que exponen las herramientas a los agentes.

RESPONSABILIDADES:
- Cargar la API Key de Google desde variables de entorno
- Crear parámetros de configuración para ejecutar servidores MCP via stdio
- Proveer función get_server_parameters() para inicializar servidores

FUNCIONAMIENTO:
Los servidores MCP se ejecutan como procesos separados que se comunican
con los agentes mediante stdio (standard input/output). Esta configuración
establece cómo iniciar esos procesos.

NOTA: Este archivo NO requiere modificación por parte de los estudiantes.
"""

from mcp import StdioServerParameters
import logging
import os 


logging.basicConfig(level = logging.INFO, format = "%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
logging.info("API KEY successfully loaded")


def get_server_parameters(server_path):
    parameters = StdioServerParameters(command = "uv", args = ["run", server_path])
    logging.info("Server Parameters successfully loaded")
    return parameters


def get_greentravel_server_parameters():
    """
    Obtiene los parámetros de configuración para el servidor MCP de GreenTravelBackend.
    
    Returns:
        StdioServerParameters: Parámetros para ejecutar el servidor greentravel_server.py
    """
    server_path = os.path.join(os.path.dirname(__file__), "greentravel_server.py")
    parameters = StdioServerParameters(command="uv", args=["run", server_path])
    logging.info("GreenTravel Server Parameters successfully loaded")
    return parameters