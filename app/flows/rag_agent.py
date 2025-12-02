"""
Workflow del Agente RAG
========================

Este módulo define el flujo de ejecución del Agente RAG utilizando LangGraph.
El agente implementa un flujo LINEAL que consulta el sistema RAG y genera una
respuesta basada en el contexto recuperado.

IMPLEMENTACIÓN SEMANA 6:
- Construir el workflow del agente RAG con LangGraph
- Definir el estado del agente (AgentState)
- Crear nodo "ask" que invoca la herramienta MCP del RAG
- Crear nodo "llm" que genera respuesta con el contexto
- Conectar los nodos en flujo lineal: ask → llm

CARACTERÍSTICAS:
- Flujo determinístico (sin ramificaciones)
- No usa bind_tools (herramienta específica recibida como parámetro)
- Siempre ejecuta la misma secuencia de pasos
"""

from typing import Annotated, Sequence, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

import logging
import sys

# Configurar logging con UTF-8
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
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

# Importación opcional para visualización del grafo
try:
    from IPython.display import Image, display
    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

# ===============================================================================
# SEMANA 6: Construir el flujo del agente RAG
# ===============================================================================

# Definir el estado del agente
class AgentState(TypedDict):
    """Estado del agente RAG que contiene la secuencia de mensajes."""
    messages: Annotated[Sequence[BaseMessage], add_messages]


def build_rag_agent(model, ask_tool):
    """
    Construye un agente RAG con flujo lineal.
    Recuerden usar la herrmaienta del MCP definida para consultar el RAG.
    
    Args:
        model: El modelo LLM (Gemini) configurado
        ask_tool: Herramienta MCP para consultar el RAG
    
    Returns:
        CompiledGraph: El grafo compilado listo para ejecutar
    """
    
    # Nodo que invoca la herramienta MCP para consultar el RAG
    async def ask_node(state: AgentState):
        """Nodo que consulta el sistema RAG usando la herramienta MCP."""
        messages = state["messages"]
        
        # Obtener la última pregunta del usuario
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            raise ValueError("El último mensaje debe ser un HumanMessage")
        
        question = last_message.content
        
        logger.info(f"[ASK NODE] Consultando RAG con pregunta: {question[:50]}...")
        
        # Invocar la herramienta MCP para consultar el RAG
        try:
            # La herramienta MCP se invoca directamente con el parámetro 'query'
            rag_context = await ask_tool.ainvoke({"query": question})
            
            # Crear un ToolMessage con el contexto recuperado
            tool_message = ToolMessage(
                content=str(rag_context),
                tool_call_id=f"rag_ask_{id(question)}"
            )
            
            logger.info(f"[ASK NODE] Contexto recuperado del RAG ({len(str(rag_context))} caracteres)")
            
            return {"messages": [tool_message]}
            
        except Exception as e:
            logger.error(f"[ASK NODE] Error al consultar RAG: {str(e)}")
            # Retornar mensaje de error como ToolMessage
            error_message = ToolMessage(
                content=f"Error al consultar el sistema RAG: {str(e)}",
                tool_call_id=f"rag_ask_error_{id(question)}"
            )
            return {"messages": [error_message]}
    
    # Nodo que genera la respuesta usando el LLM
    async def llm_node(state: AgentState):
        """Nodo que genera la respuesta final usando el LLM con el contexto del RAG."""
        messages = state["messages"]
        
        logger.info(f"[LLM NODE] Generando respuesta con {len(messages)} mensajes en el contexto")
        
        # Extraer la pregunta del usuario y el contexto del RAG
        human_message = None
        rag_context = None
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                human_message = msg
            elif isinstance(msg, ToolMessage):
                rag_context = msg.content
        
        # Construir mensajes para el LLM con instrucciones claras
        llm_messages = []
        
        # Agregar mensaje del sistema con instrucciones
        system_prompt = """Eres un asistente que responde preguntas basándote ÚNICAMENTE en el contexto proporcionado del sistema RAG.

INSTRUCCIONES:
- Usa SOLO la información del contexto proporcionado para responder la pregunta
- Si el contexto contiene la respuesta, úsala directamente
- Si el contexto no tiene suficiente información, indica que no tienes esa información específica
- Sé preciso y conciso en tu respuesta, simpre incluir el numero o codigo de la factura, liquidacion o servicio turistico completo.
- No inventes información que no esté en el contexto
- Entrega un formato de respuesta claro y estructurado usando Markdown.

"""
        
        llm_messages.append(SystemMessage(content=system_prompt))
        
        # Agregar el contexto del RAG si está disponible
        if rag_context:
            context_message = f"""CONTEXTO RECUPERADO DEL RAG:
{rag_context}

PREGUNTA DEL USUARIO: {human_message.content if human_message else 'N/A'}

Responde la pregunta del usuario basándote ÚNICAMENTE en el contexto proporcionado arriba."""
            llm_messages.append(HumanMessage(content=context_message))
        else:
            # Si no hay contexto, usar el mensaje original del usuario
            if human_message:
                llm_messages.append(human_message)
        
        # Invocar el modelo LLM con los mensajes estructurados
        response = await model.ainvoke(llm_messages)
        
        logger.info(f"[LLM NODE] Respuesta generada exitosamente")
        
        return {"messages": [response]}
    
    # Construir el grafo
    graph = StateGraph(AgentState)
    
    # Agregar nodos
    graph.add_node("ask", ask_node)
    graph.add_node("llm", llm_node)
    
    # Conectar los nodos en flujo lineal: START → ask → llm → END
    graph.add_edge(START, "ask")
    graph.add_edge("ask", "llm")
    graph.add_edge("llm", END)
    
    # Compilar y retornar el grafo
    compiled_graph = graph.compile()
    
    logger.info("RAG Agent workflow compilado exitosamente")
    
    return compiled_graph


def visualize_graph(graph_instance=None):
    """
    Genera una visualización del grafo RAG.
    
    Args:
        graph_instance: Instancia del grafo compilado (opcional)
    
    Returns:
        str: Ruta al archivo de imagen generado o None si falla
    """
    import os
    from pathlib import Path
    
    try:
        if graph_instance is None:
            # Crear una instancia del grafo para visualización
            from mcp_server.model import llm
            # Crear un mock tool para visualización
            from langchain_core.tools import tool
            
            @tool
            async def mock_ask_tool(query: str) -> str:
                """Mock tool para visualización."""
                return "Mock response"
            
            graph_instance = build_rag_agent(llm, mock_ask_tool)
        
        # Obtener el grafo visual
        graph_image = graph_instance.get_graph().draw_mermaid_png()
        
        # Guardar la imagen
        images_dir = Path(__file__).parent.parent / "images"
        images_dir.mkdir(exist_ok=True)
        
        output_path = images_dir / "rag_agent_graph.png"
        with open(output_path, "wb") as f:
            f.write(graph_image)
        
        logger.info(f"Grafo visualizado y guardado en: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.warning(f"No se pudo visualizar el grafo: {e}")
        return None


# ===============================================================================
# Función para LangGraph Studio/Deployment
# ===============================================================================

def graph(config=None):
    """
    Función que construye y retorna el grafo RAG para LangGraph Studio/Deployment.
    
    Esta función es llamada por LangGraph CLI cuando se especifica en langgraph.json.
    Para LangGraph Studio, crea un grafo con un mock tool ya que MCP se inicializa
    en tiempo de ejecución a través del servicio.
    
    Args:
        config: RunnableConfig opcional (no usado actualmente, pero requerido por la API)
    
    Returns:
        CompiledGraph: El grafo compilado listo para ejecutar
    """
    from mcp_server.model import llm
    from langchain_core.tools import tool
    
    # Crear un mock tool para visualización en LangGraph Studio
    # En tiempo de ejecución real, el servicio inicializa MCP correctamente
    @tool
    async def mock_ask_tool(query: str) -> str:
        """
        Mock tool para visualización del grafo en LangGraph Studio.
        En producción, este tool es reemplazado por la herramienta MCP real.
        
        Args:
            query: La pregunta del usuario
        
        Returns:
            str: Respuesta mock del RAG
        """
        return "Mock RAG response - En producción se usa la herramienta MCP real"
    
    # Construir el grafo usando la función existente
    compiled_graph = build_rag_agent(llm, mock_ask_tool)
    
    logger.info("Grafo RAG construido para LangGraph Studio/Deployment")
    
    return compiled_graph
