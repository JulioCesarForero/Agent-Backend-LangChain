"""
Servicio del Agente GreenTravelBackend
=======================================

Este módulo gestiona el ciclo de vida del Agente GreenTravelBackend, incluyendo
la inicialización de la sesión MCP, carga de herramientas y ejecución del agente
para procesar consultas sobre Liquidaciones y Proveedores.
"""

from langchain_core.messages import HumanMessage, AIMessage
from flows.greentravel_agent import build_greentravel_agent
from mcp.client.stdio import stdio_client
from mcp_server.tools import load_tools
from mcp_server.model import llm
from mcp import ClientSession
import asyncio
import logging


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class GreenTravelAgentService:

    def __init__(self):
        self.server_parameters = None
        self._lock = asyncio.Lock()
        self._stdio_ctx = None
        self._session = None
        self.agent = None

    def set_server_parameters(self, server_parameters):
        self.server_parameters = server_parameters

    async def initialize(self):
        """
        Inicializa la sesión MCP y construye el agente GreenTravelBackend.
        """
        async with self._lock:
            if self._session is None:
                if not self.server_parameters:
                    raise ValueError("MCP server parameters not set. Call set_server_parameters() first")
                
                logger.info("Starting stdio_client for GreenTravelBackend...")
                self._stdio_ctx = stdio_client(self.server_parameters)
                read, write = await self._stdio_ctx.__aenter__()
                self._session = await ClientSession(read, write).__aenter__()
                await self._session.initialize()
                logger.info("MCP session initialized successfully")

                # Cargar herramientas del MCP server
                tools, tools_by_name = await load_tools(self._session)
                logger.info(f"Loaded {len(tools)} tools from MCP server")
                
                # Filtrar solo las herramientas de GreenTravelBackend (incluyendo facturas)
                greentravel_tools = [
                    # Liquidaciones
                    "list_liquidaciones", "get_liquidacion", "create_liquidacion",
                    "update_liquidacion", "delete_liquidacion", "get_liquidacion_stats",
                    # Proveedores
                    "list_provedores", "get_provedor", "create_provedor",
                    "update_provedor", "delete_provedor", "get_provedor_stats",
                    # Facturas
                    "rag_get_invoice_data", "calcular_vencimiento"
                ]
                
                filtered_tools = [t for t in tools if t.name in greentravel_tools]
                filtered_tools_by_name = {name: tool for name, tool in tools_by_name.items() if name in greentravel_tools}
                
                logger.info(f"Using GreenTravelBackend tools: {list(filtered_tools_by_name.keys())}")
                
                # Verificar que tenemos al menos algunas herramientas
                if not filtered_tools:
                    logger.warning("No GreenTravelBackend tools found. Available tools: " + ", ".join(tools_by_name.keys()))
                    # Usar todas las herramientas como fallback
                    filtered_tools = tools
                    filtered_tools_by_name = tools_by_name

                # Construir el agente con las herramientas filtradas
                self.agent = build_greentravel_agent(
                    llm.bind_tools(filtered_tools), 
                    filtered_tools_by_name
                )
                
                logger.info("GreenTravelBackend Agent created successfully")

    async def ask_greentravel(self, question):
        """
        Procesa una pregunta usando el agente GreenTravelBackend.
        
        Args:
            question (str): La pregunta o tarea del usuario
        
        Returns:
            str: La respuesta generada por el agente
        """
        # Asegurarse de que el agente está inicializado
        if self._session is None or self.agent is None:
            await self.initialize()
        
        logger.info(f"[GREEN TRAVEL SERVICE] Processing question: {question}")

        # Crear un HumanMessage con la pregunta del usuario
        human_message = HumanMessage(content=question)
        
        # Invocar el agente con el mensaje inicial
        state = {
            "messages": [human_message]
        }
        
        result = await self.agent.ainvoke(state)

        # Extraer el último mensaje (AIMessage) que contiene la respuesta final
        messages = result.get("messages", [])
        if not messages:
            raise ValueError("El agente no retornó ningún mensaje")

        # El último mensaje es la respuesta del LLM
        last_message = messages[-1]

        # Verificar que es un AIMessage
        if not isinstance(last_message, AIMessage):
            raise ValueError(f"El último mensaje no es un AIMessage: {type(last_message)}")

        # Extraer el contenido de la respuesta
        answer = last_message.content

        logger.info(f"[GREEN TRAVEL SERVICE] Respuesta generada exitosamente ({len(answer)} caracteres)")

        return answer

    async def shutdown(self):
        """
        Cierra la sesión MCP y limpia recursos.
        """
        async with self._lock:
            if self._session:
                await self._session.__aexit__(None, None, None)
                self._session = None
            if self._stdio_ctx:
                await self._stdio_ctx.__aexit__(None, None, None)
                self._stdio_ctx = None
            logger.debug("MCP session and stdio_client shut down")


GREEN_TRAVEL_AGENT_SERVICE = GreenTravelAgentService()

