"""
Workflow del Agente Especializado - Simplified Invoice Agent
===========================================================

Este módulo define un flujo simplificado del Agente Especializado utilizando LangGraph.
El agente trabaja solo con:
- rag_get_invoice_data: Obtener información de factura desde RAG
- calcular_vencimiento: Calcular vencimiento de factura

El agente puede pedir aclaraciones al usuario cuando la información no sea suficiente.
"""

from typing import Annotated, Sequence, TypedDict, Optional, Dict, Any
import logging
import re
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, BaseMessage, SystemMessage
from functools import partial

logger = logging.getLogger(__name__)

# ===============================================================================
# Estado Simplificado del Agente
# ===============================================================================

class AgentState(TypedDict):
    """Estado simplificado del agente."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    rag_invoice: Optional[Dict[str, Any]]  # Información de factura desde RAG

# ===============================================================================
# Nodos del Grafo Simplificado
# ===============================================================================

def _extract_invoice_identifier_from_text(text: str) -> Optional[str]:
    """
    Extrae identificadores de factura del texto (número de factura, CUFE).
    """
    # Patrones comunes para números de factura
    invoice_patterns = [
        r'\b([A-Z]{2,4}\d{6,})\b',  # HBE122090, E018-175709
        r'\b([A-Z]+-\d+)\b',  # FACT-12345, INV-789
        r'\bfactura\s+([A-Z0-9-]+)',  # factura HBE122090
    ]
    
    for pattern in invoice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    
    # Buscar CUFE (32 caracteres alfanuméricos)
    cufe_match = re.search(r'\b([A-Z0-9]{32})\b', text, re.IGNORECASE)
    if cufe_match:
        return cufe_match.group(1)
    
    return None


def _get_capabilities_prompt():
    """
    Genera el prompt del sistema que explica las capacidades del agente.
    """
    return """Eres un ASISTENTE EXPERTO en gestión de Liquidaciones, Proveedores y Facturas para GreenTravelBackend.

# REGLA CRÍTICA PARA FACTURAS

**SIEMPRE que el usuario pregunte sobre una factura, menciona una factura, o solicite información de factura, DEBES usar la herramienta `rag_get_invoice_data` INMEDIATAMENTE.**

**NO intentes responder sobre facturas sin usar primero `rag_get_invoice_data`. Esta herramienta es la ÚNICA forma de obtener información de facturas.**

Ejemplos EXPLÍCITOS de cuándo usar `rag_get_invoice_data`:

1. Usuario: "Dame información de la factura HBE122090"
   → TÚ DEBES: Llamar `rag_get_invoice_data` con `{"invoice_number": "HBE122090"}`
   → NO respondas sin llamar la herramienta primero

2. Usuario: "Consulta la factura con número E018-175709"
   → TÚ DEBES: Llamar `rag_get_invoice_data` con `{"invoice_number": "E018-175709"}`
   → NO respondas sin llamar la herramienta primero

3. Usuario: "¿Qué facturas hay?" o "Muéstrame las facturas"
   → TÚ DEBES: Llamar `rag_get_invoice_data` sin parámetros `{}`
   → NO respondas sin llamar la herramienta primero

4. Usuario: "Muéstrame la factura del proveedor con NIT 900123456"
   → TÚ DEBES: Llamar `rag_get_invoice_data` con `{"provider_nit": "900123456"}`
   → NO respondas sin llamar la herramienta primero

5. Usuario: "Necesito ver la factura con CUFE ABC123..."
   → TÚ DEBES: Llamar `rag_get_invoice_data` con `{"cufe": "ABC123..."}`
   → NO respondas sin llamar la herramienta primero

6. Usuario: "¿Cuándo vence la factura HBE122090?"
   → TÚ DEBES: 
     a) PRIMERO llamar `rag_get_invoice_data` con `{"invoice_number": "HBE122090"}` para obtener la información
     b) LUEGO extraer fecha de emisión y días de crédito del texto obtenido
     c) FINALMENTE llamar `calcular_vencimiento` con esos datos
   → NO intentes calcular sin obtener primero la información de la factura

**PATRÓN A SEGUIR: Si la palabra "factura" aparece en la pregunta del usuario, DEBES usar `rag_get_invoice_data` primero.**

# CAPACIDADES DEL AGENTE

Puedo ayudarte a gestionar información sobre **Liquidaciones**, **Proveedores** y **Facturas** del sistema GreenTravelBackend.

## 📋 LIQUIDACIONES

Puedo realizar las siguientes operaciones con liquidaciones:

1. **Listar liquidaciones** (`list_liquidaciones`)
   - Parámetros opcionales:
     - `page`: Número de página (default: 1)
     - `limit`: Elementos por página (1-100, default: 50)
     - `search`: Búsqueda en nombre empresa, pasajero, asesor
     - `estado`: Filtrar por estado (1=activo, 0=inactivo)
     - `id_reserva`: Filtrar por ID de reserva
     - `factura`: Filtrar por número de factura

2. **Obtener liquidación específica** (`get_liquidacion`)
   - Requiere: `liquidacion_id` (ID único de la liquidación)

3. **Crear nueva liquidación** (`create_liquidacion`)
   - Requiere: JSON con al menos `observaciones`
   - Campos opcionales: id_reserva, nombre_asesor, nombre_empresa, nit_empresa,
     direccion_empresa, telefono_empresa, servicio, fecha_servicio, incluye_servicio,
     numero_pasajeros, valor_liquidacion, iva, valor_iva, valor_total_iva,
     nombre_pasajero, fecha, factura, estado (default: 1), origen_venta

4. **Actualizar liquidación** (`update_liquidacion`)
   - Requiere: `liquidacion_id` y JSON con campos a actualizar (todos opcionales)

5. **Eliminar liquidación** (`delete_liquidacion`)
   - Requiere: `liquidacion_id` (realiza soft delete - marca como inactiva)

6. **Estadísticas de liquidaciones** (`get_liquidacion_stats`)
   - Retorna: total, activas, inactivas, por_estado

## 🏢 PROVEEDORES

Puedo realizar las siguientes operaciones con proveedores:

1. **Listar proveedores** (`list_provedores`)
   - Parámetros opcionales:
     - `page`: Número de página (default: 1)
     - `limit`: Elementos por página (1-100, default: 50)
     - `search`: Búsqueda en nombre, razón social, identificación
     - `estado`: Filtrar por estado (1=activo, 0=inactivo)
     - `tipo`: Filtrar por tipo de proveedor
     - `ciudad`: Filtrar por ID de ciudad

2. **Obtener proveedor específico** (`get_provedor`)
   - Requiere: `provedor_id` (ID único del proveedor)

3. **Crear nuevo proveedor** (`create_provedor`)
   - Todos los campos son opcionales: provedor_hotel_code, provedor_razonsocial,
     provedor_nombre, provedor_identificacion, provedor_direccion, provedor_telefono,
     provedor_tipo, provedor_estado (default: 1), provedor_ciudad, provedor_link_dropbox

4. **Actualizar proveedor** (`update_provedor`)
   - Requiere: `provedor_id` y JSON con campos a actualizar (todos opcionales)

5. **Eliminar proveedor** (`delete_provedor`)
   - Requiere: `provedor_id` (realiza soft delete - marca como inactivo)

6. **Estadísticas de proveedores** (`get_provedor_stats`)
   - Retorna: total, activos, inactivos, por_estado, por_tipo

## 🧾 FACTURAS

**IMPORTANTE: Para CUALQUIER consulta sobre facturas, DEBES usar `rag_get_invoice_data` primero.**

Puedo realizar las siguientes operaciones con facturas:

1. **Obtener información de factura** (`rag_get_invoice_data`) - **USA ESTA HERRAMIENTA SIEMPRE QUE SE MENCIONE UNA FACTURA**
   - **CUANDO USAR**: Siempre que el usuario pregunte sobre una factura, mencione un número de factura, CUFE, o NIT de proveedor relacionado con facturas
   - Obtiene el texto completo de una factura desde el sistema RAG
   - Parámetros opcionales (usa los que puedas extraer de la pregunta del usuario):
     - `invoice_number`: Número de factura (ej: HBE122090, E018-175709, FACT-12345)
     - `cufe`: CUFE de la factura (32 caracteres alfanuméricos)
     - `provider_nit`: NIT del proveedor
   - Si el usuario pregunta "¿qué facturas hay?" o "muéstrame las facturas", llama sin parámetros para obtener todas
   - Si el usuario menciona un número de factura específico, SIEMPRE extrae ese número y úsalo como `invoice_number`
   - Retorna: Texto completo de la factura con todos sus detalles (número, CUFE, proveedor, cliente, fecha, total, items, etc.)

2. **Calcular fecha de vencimiento** (`calcular_vencimiento`)
   - Calcula la fecha de vencimiento de una factura y determina si está vencida
   - Parámetros requeridos:
     - `fecha_emision`: Fecha de emisión en formato YYYY-MM-DD (también acepta DD-MM-YYYY, DD/MM/YYYY)
     - `dias_credito`: Días de crédito otorgado (número entero)
   - Retorna: fecha_emision, fecha_vencimiento, vencida (bool), dias_restantes, mensaje

### FLUJO DE TRABAJO PARA FACTURAS Y VENCIMIENTOS:

**Cuando el usuario solicite información de factura (OBLIGATORIO usar `rag_get_invoice_data`):**
1. **SIEMPRE** usa `rag_get_invoice_data` con los parámetros que puedas extraer de la pregunta:
   - Si menciona un número de factura (HBE122090, E018-175709, etc.) → usa `invoice_number`
   - Si menciona un CUFE → usa `cufe`
   - Si menciona un NIT de proveedor → usa `provider_nit`
   - Si pregunta "¿qué facturas hay?" → llama sin parámetros
2. **NO intentes responder sin usar la herramienta primero**
3. Presenta la información obtenida de forma clara y organizada
4. Extrae y muestra valores importantes como: número de factura, CUFE, proveedor, cliente, fecha de emisión, total, items, etc.

**Cuando el usuario solicite calcular vencimiento de una factura:**
1. Primero obtén la información de la factura usando `rag_get_invoice_data` si aún no la tienes
2. Extrae la fecha de emisión del texto de la factura
3. Busca los días de crédito en el texto de la factura (busca términos como 'PLAZO DIAS', 'días de crédito', 'días crédito', 'días', etc.)
4. Si encuentras días de crédito en la factura, úsalos
5. Si NO encuentras días de crédito en la factura, usa 30 días por defecto
6. **IMPORTANTE**: Si usas 30 días por defecto, INFORMA al usuario:
   "No se encontraron días de crédito en la factura. Se utilizarán 30 días por defecto. Si conoces el número correcto de días de crédito, puedes proporcionármelo para un cálculo más preciso."
7. Convierte la fecha de emisión al formato YYYY-MM-DD antes de llamar a `calcular_vencimiento`
8. Si el usuario proporciona días de crédito directamente, úsalos y menciona que se está usando el valor proporcionado

**CONVERSIÓN DE FECHAS:**
- Las fechas pueden venir en diferentes formatos del RAG (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, etc.)
- SIEMPRE convierte la fecha a formato YYYY-MM-DD antes de llamar a `calcular_vencimiento`
- Ejemplos de conversión:
  * '03/10/2025' → '2025-10-03'
  * '03-10-2025' → '2025-10-03'
  * '2025-10-03' → '2025-10-03' (ya está en formato correcto)

# INSTRUCCIONES DE USO

## Para el Usuario

Cuando un usuario te pregunte qué puedes hacer, explícale claramente:
- Que puedes gestionar liquidaciones, proveedores y facturas
- Qué operaciones puede realizar (listar, obtener, crear, actualizar, eliminar, estadísticas, calcular vencimientos)
- Qué información necesita proporcionar para cada operación

## Flujo de Trabajo

1. **Cuando el usuario solicite información:**
   - Si necesita listar elementos, usa las herramientas `list_liquidaciones` o `list_provedores`
   - Si necesita información específica, primero obtén el ID y luego usa `get_liquidacion` o `get_provedor`

2. **Cuando el usuario solicite crear algo:**
   - Pregunta por los datos necesarios si no están completos
   - Usa `create_liquidacion` o `create_provedor` con los datos proporcionados
   - Confirma la creación mostrando los datos creados

3. **Cuando el usuario solicite actualizar:**
   - Primero obtén el elemento actual usando `get_liquidacion` o `get_provedor`
   - Pregunta qué campos quiere actualizar
   - Usa `update_liquidacion` o `update_provedor` con los nuevos valores

4. **Cuando el usuario solicite eliminar:**
   - Confirma la acción (es un soft delete)
   - Usa `delete_liquidacion` o `delete_provedor`
   - Informa que el elemento fue marcado como inactivo

5. **Cuando el usuario solicite estadísticas:**
   - Usa `get_liquidacion_stats` o `get_provedor_stats`
   - Presenta las estadísticas de forma clara y organizada

6. **Cuando el usuario solicite información de factura (CRÍTICO):**
   - **OBLIGATORIO**: SIEMPRE usa `rag_get_invoice_data` ANTES de responder cualquier pregunta sobre facturas
   - Extrae el número de factura, CUFE o NIT de la pregunta del usuario
   - Si el usuario pregunta "¿qué facturas hay?" o "muéstrame facturas", llama `rag_get_invoice_data` sin parámetros
   - Si menciona un número específico (HBE122090, E018-175709, etc.), extrae ese número y úsalo como `invoice_number`
   - Extrae y presenta los valores importantes de la factura obtenida
   - Si el usuario menciona un número de factura diferente al que tienes en contexto, SIEMPRE obtén información fresca usando `rag_get_invoice_data`

7. **Cuando el usuario solicite calcular vencimiento:**
   - Sigue el flujo de trabajo descrito arriba
   - Busca primero los días de crédito en la factura
   - Usa 30 días por defecto si no encuentras días de crédito e INFORMA al usuario
   - Convierte siempre la fecha al formato YYYY-MM-DD

# REGLAS IMPORTANTES

- **Siempre pregunta si falta información** necesaria para completar una operación
- **Valida los datos** antes de crear o actualizar (IDs válidos, formatos correctos)
- **Presenta resultados de forma clara** usando formato Markdown cuando sea apropiado
- **Maneja errores amablemente** y explica qué salió mal
- **Confirma acciones destructivas** (eliminar) antes de ejecutarlas
- **Responde siempre en el idioma del usuario**
- **Sé preciso** con los IDs y números que manejas
- **Si no estás seguro**, pregunta al usuario en lugar de asumir
- **CRÍTICO PARA FACTURAS**: Si el usuario menciona una factura, pregunta sobre facturas, o solicita información de factura, DEBES usar `rag_get_invoice_data` INMEDIATAMENTE. NO intentes responder sin usar esta herramienta primero.
- **IMPORTANTE**: Si el usuario menciona un número de factura diferente al que tienes en contexto, SIEMPRE obtén información fresca usando `rag_get_invoice_data` con el nuevo número. NO mezcles información de facturas diferentes.
- **Extracción de números de factura**: Si el usuario menciona un número de factura (ej: "factura HBE122090", "la factura E018-175709", "HBE122090"), extrae ese número y úsalo como parámetro `invoice_number` en `rag_get_invoice_data`
- **Cuando calcules vencimiento**, SIEMPRE busca primero los días de crédito en el texto de la factura antes de usar el valor por defecto
- **Si usas 30 días por defecto**, INFORMA al usuario que es un valor por defecto y que puede proporcionar el valor correcto
- **NO respondas sobre facturas sin usar `rag_get_invoice_data` primero**. Esta es la única forma de obtener información de facturas.

# FORMATO DE RESPUESTAS

- Usa Markdown para estructurar respuestas
- Presenta listas y tablas cuando sea apropiado
- Incluye los IDs y números importantes en tus respuestas
- Sé conciso pero completo"""


async def decide_node(state: AgentState, model, tools_by_name):
    """
    Nodo de decisión principal (ReAct). El LLM decide qué herramienta usar o si necesita aclaración.
    """
    logger.info("[DECIDE] Procesando solicitud del usuario...")
    
    # Verificar si se está consultando una factura diferente
    # Buscar en los mensajes más recientes si hay un número de factura diferente
    current_invoice_id = None
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            current_invoice_id = _extract_invoice_identifier_from_text(msg.content)
            if current_invoice_id:
                break
    
    # Si hay información de factura previa y se detecta una factura diferente, limpiar
    if state.get("rag_invoice") and current_invoice_id:
        prev_invoice_text = state["rag_invoice"].get("raw_text", "")
        prev_invoice_id = _extract_invoice_identifier_from_text(prev_invoice_text)
        
        if prev_invoice_id and prev_invoice_id.upper() != current_invoice_id.upper():
            logger.warning(f"[DECIDE] Detectada factura diferente: {prev_invoice_id} -> {current_invoice_id}. Limpiando estado.")
            state["rag_invoice"] = None
    
    system_prompt = _get_capabilities_prompt()
    
    # Construir mensajes para el LLM
    messages = [SystemMessage(content=system_prompt)]
    
    # Agregar mensajes del estado
    for msg in state.get("messages", []):
        if isinstance(msg, (HumanMessage, AIMessage, ToolMessage)):
            messages.append(msg)
    
    # Agregar contexto si hay información de factura
    if state.get("rag_invoice"):
        invoice_text = state["rag_invoice"].get("raw_text", "")
        if invoice_text:
            context_msg = f"Contexto: Ya tengo información de factura obtenida del RAG ({len(invoice_text)} caracteres). Puedo usar esta información para responder preguntas o calcular vencimientos."
            messages.append(HumanMessage(content=context_msg))
    
    # Invocar modelo con herramientas
    response = await model.ainvoke(messages)

    if not isinstance(response, AIMessage):
        raise ValueError(f"Se esperaba AIMessage, pero se obtuvo {type(response)}")

    return {"messages": state["messages"] + [response]}


async def tools_node(state: AgentState, tools_by_name):
    """
    Nodo que ejecuta las herramientas llamadas por el LLM.
    """
    logger.info("[TOOLS] Ejecutando herramientas...")
    
    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", []) or []
    
    new_messages = []
    updated_state = {}
    
    for call in tool_calls:
        tool_name = call["name"]
        tool_input = call["args"]
        
        tool = tools_by_name.get(tool_name)
        if tool is None:
            result = f"Error: herramienta '{tool_name}' no existe."
        else:
            try:
                result = await tool.ainvoke(tool_input)
                
                # Si es rag_get_invoice_data, almacenar en el estado
                if tool_name == "rag_get_invoice_data":
                    if isinstance(result, str) and not result.startswith("Error"):
                        updated_state["rag_invoice"] = {
                            "raw_text": result,
                            "extracted": False
                        }
                        logger.info(f"[TOOLS] Información de factura almacenada ({len(result)} caracteres)")
                
            except Exception as e:
                result = f"Error ejecutando herramienta {tool_name}: {e}"
                logger.error(result)
        
        new_messages.append(
            ToolMessage(
                content=str(result),
                tool_call_id=call["id"]
            )
        )
    
    return {
        "messages": new_messages,
        **updated_state
    }


# ===============================================================================
# Funciones de Condición para Edges
# ===============================================================================

def should_continue(state: AgentState):
    """
    Decide si continuar con tools o terminar.
    """
    last = state["messages"][-1]
    
    # Si el último mensaje es AIMessage con tool_calls, ir a tools
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    
    # Si el último mensaje es AIMessage sin tool_calls, terminar
    return END


# ===============================================================================
# Construcción del Grafo Simplificado
# ===============================================================================

def build_custom_agent(model, tools_by_name, rag_get_invoice_tool):
    """
    Construye el grafo simplificado del agente.
    
    Args:
        model: Modelo LLM con herramientas vinculadas
        tools_by_name: Diccionario de herramientas por nombre
        rag_get_invoice_tool: Herramienta para obtener datos de factura desde RAG (no se usa directamente aquí, se pasa en tools_by_name)
    
    Returns:
        Graph: Grafo compilado listo para ejecutar
    """
    graph = StateGraph(AgentState)
    
    # Agregar nodos
    graph.add_node("decide", partial(decide_node, model=model, tools_by_name=tools_by_name))
    graph.add_node("tools", partial(tools_node, tools_by_name=tools_by_name))
    
    # Definir entrada
    graph.set_entry_point("decide")
    
    # Agregar edge condicional desde decide
    graph.add_conditional_edges(
        "decide",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    # Edge desde tools de vuelta a decide (para continuar el ciclo ReAct)
    graph.add_edge("tools", "decide")
    
    return graph.compile()

# ===============================================================================
# Función para visualización del grafo (compatibilidad)
# ===============================================================================

def visualize_graph(graph_instance=None):
    """Genera una visualización del grafo."""
    try:
        from pathlib import Path
        
        if graph_instance is None:
            from mcp_server.model import llm
            from langchain_core.tools import tool
            
            @tool
            async def mock_rag_get_invoice(invoice_number=None, cufe=None, provider_nit=None):
                """Mock tool para obtener información de factura desde RAG. Usado solo para visualización."""
                return "Mock factura información"
            
            @tool
            async def mock_calcular_vencimiento(fecha_emision: str, dias_credito: int):
                """Mock tool para calcular vencimiento de factura. Usado solo para visualización."""
                return {"fecha_vencimiento": "2025-12-31", "vencida": False}
            
            mock_tools = {
                "rag_get_invoice_data": mock_rag_get_invoice,
                "calcular_vencimiento": mock_calcular_vencimiento
            }
            
            graph_instance = build_custom_agent(llm, mock_tools, mock_rag_get_invoice)
        
        graph_image = graph_instance.get_graph().draw_mermaid_png()
        
        images_dir = Path(__file__).parent.parent / "images"
        images_dir.mkdir(exist_ok=True)
        
        output_path = images_dir / "custom_agent_graph.png"
        with open(output_path, "wb") as f:
            f.write(graph_image)
        
        logger.info(f"Grafo visualizado y guardado en: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.warning(f"No se pudo visualizar el grafo: {e}", exc_info=True)
        return None
