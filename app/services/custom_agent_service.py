"""
Servicio del Agente Especializado
==================================

Este módulo gestiona el ciclo de vida del Agente Especializado (ReAct), incluyendo
la inicialización de la sesión MCP, carga de múltiples herramientas y ejecución
del agente para procesar tareas complejas de los usuarios.

IMPLEMENTACIÓN SEMANA 7:
- Completar el método ask_custom para invocar el agente ReAct
- Pasar la pregunta del usuario al agente compilado
- Extraer el último mensaje (respuesta final) del resultado
- Retornar el string de la respuesta final
"""

from langchain_core.messages import HumanMessage, AIMessage
from flows.custom_agent import build_custom_agent
from mcp.client.stdio import stdio_client
from mcp_server.tools import load_tools
from mcp_server.model import llm
from mcp import ClientSession
import asyncio
import logging
import re
import hashlib
from typing import Optional
from langgraph.checkpoint.memory import MemorySaver



logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CustomAgentService:


    def __init__(self):
        self.server_parameters = None
        self._lock = asyncio.Lock()
        self._stdio_ctx = None
        self._session = None
        self.agent = None
        self.checkpointer = MemorySaver()  # Persistencia de estado para HITL

    
    def set_server_parameters(self, server_parameters):
        self.server_parameters = server_parameters
    

    async def initialize(self):
        """
        Inicializa la sesión MCP y construye el agente personalizado.
        
        NOTA: Este método ya está implementado y NO necesita modificación.
        """
        async with self._lock:
            if self._session is None:
                if not self.server_parameters:
                    raise ValueError("MCP server parameters not set. Call set_server_parameters() first")
                
                logger.info("Starting stdio_client...")
                self._stdio_ctx = stdio_client(self.server_parameters)
                read, write = await self._stdio_ctx.__aenter__()
                self._session = await ClientSession(read, write).__aenter__()
                await self._session.initialize()
                logger.info("MCP session initialized successfully")

                # Cargar herramientas del MCP server
                tools, tools_by_name = await load_tools(self._session)
                logger.info(f"Loaded {len(tools)} tools from MCP server")
                
                # Filtrar herramientas de GreenTravelBackend (liquidaciones, proveedores, facturas)
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
                
                # Obtener la herramienta rag_get_invoice_data específica
                rag_get_invoice_tool = filtered_tools_by_name.get("rag_get_invoice_data")

                # Construir el agente con todas las herramientas
                # NOTA: build_custom_agent ya retorna un grafo compilado, no necesita compilarse de nuevo
                self.agent = build_custom_agent(
                    llm.bind_tools(filtered_tools), 
                    filtered_tools_by_name, 
                    rag_get_invoice_tool=rag_get_invoice_tool
                )
                
                # El agente ya está compilado por build_custom_agent
                # Si necesitamos agregar checkpointer, necesitaríamos modificar build_custom_agent
                # Por ahora, el agente funciona sin checkpointer adicional
                
                logger.info("Simplified Custom Agent created successfully")
    

    # ===============================================================================
    # SEMANA 7: Implementar la ejecución del agente personalizado
    # ===============================================================================
    

    def _extract_invoice_identifier(self, question: str) -> Optional[str]:
        """
        Extrae identificadores de factura de la pregunta (número de factura, CUFE, NIT).
        Retorna un identificador único basado en lo encontrado.
        """
        # Patrones comunes para números de factura
        # Ejemplos: HBE122090, E018-175709, FACT-12345, etc.
        invoice_patterns = [
            r'\b([A-Z]{2,4}\d{6,})\b',  # HBE122090, E018-175709
            r'\b([A-Z]+-\d+)\b',  # FACT-12345, INV-789
            r'\bfactura\s+([A-Z0-9-]+)',  # factura HBE122090
            r'\b([A-Z]{2}\d{9})\b',  # CUFE (32 caracteres alfanuméricos, pero buscamos patrones comunes)
        ]
        
        for pattern in invoice_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                invoice_id = match.group(1) if match.lastindex else match.group(0)
                logger.info(f"[CUSTOM SERVICE] Invoice identifier found: {invoice_id}")
                return invoice_id
        
        # Buscar CUFE (32 caracteres alfanuméricos)
        cufe_match = re.search(r'\b([A-Z0-9]{32})\b', question, re.IGNORECASE)
        if cufe_match:
            logger.info(f"[CUSTOM SERVICE] CUFE found: {cufe_match.group(1)}")
            return cufe_match.group(1)
        
        return None

    def _generate_thread_id(self, question: str) -> str:
        """
        Genera un thread_id único basado en el identificador de factura encontrado,
        o en un hash de la pregunta si no se encuentra factura específica.
        Esto evita mezclar información entre diferentes facturas.
        """
        invoice_id = self._extract_invoice_identifier(question)
        
        if invoice_id:
            # Usar el identificador de factura como parte del thread_id
            # Esto agrupa consultas sobre la misma factura
            thread_id = f"invoice_{invoice_id.lower().replace('-', '_')}"
            logger.info(f"[CUSTOM SERVICE] Using invoice-specific thread_id: {thread_id}")
            return thread_id
        else:
            # Si no hay factura específica, usar un hash de la pregunta
            # Esto crea un thread único por consulta diferente
            question_hash = hashlib.md5(question.encode()).hexdigest()[:8]
            thread_id = f"query_{question_hash}"
            logger.info(f"[CUSTOM SERVICE] Using query-specific thread_id: {thread_id}")
            return thread_id

    async def ask_custom(self, question):
            """
            Procesa una pregunta usando el agente personalizado ReAct.
            
            Args:
                question (str): La pregunta o tarea del usuario
            
            Returns:
                str: La respuesta generada por el agente
            """
            # Asegurarse de que el agente está inicializado
            if self._session is None or self.agent is None:
                await self.initialize()
            
            logger.info(f"[CUSTOM SERVICE] Processing question: {question}")

            # ======================================
            # 1. Generar thread_id único basado en la factura o consulta
            # ======================================
            thread_id = self._generate_thread_id(question)

            # ======================================
            # 2. Preparar estado inicial del agente (siempre limpio)
            # ======================================
            # IMPORTANTE: Siempre empezar con rag_invoice=None para evitar mezclar información
            # entre diferentes facturas. El agente obtendrá la información fresca del RAG.
            state = {
                "messages": [HumanMessage(content=question)],
                "rag_invoice": None  # Siempre limpiar al inicio de cada consulta
            }
            
            logger.info(f"[CUSTOM SERVICE] Starting with clean state (rag_invoice=None)")

            # ======================================
            # 3. Ejecutar el agente con configuración de checkpoint
            # ======================================
            config = {"configurable": {"thread_id": thread_id}}
            result = await self.agent.ainvoke(state, config=config)

            # ======================================
            # 3. Extraer el último mensaje como respuesta final
            # ======================================
            messages = result.get("messages", [])

            if not messages:
                return "No se generó ninguna respuesta."

            last_msg = messages[-1]

            # A veces la respuesta final es AIMessage(content=xxx)
            if hasattr(last_msg, "content"):
                return last_msg.content

            # Fallback en caso de formatos no previstos
            return str(last_msg)


    async def shutdown(self):
        """
        Cierra la sesión MCP y limpia recursos.
        
        NOTA: Este método ya está implementado y NO necesita modificación.
        """
        async with self._lock:
            if self._session:
                await self._session.__aexit__(None, None, None)
                self._session = None
            if self._stdio_ctx:
                await self._stdio_ctx.__aexit__(None, None, None)
                self._stdio_ctx = None
            logger.debug("MCP session and stdio_client shut down")


CUSTOM_AGENT_SERVICE = CustomAgentService()
