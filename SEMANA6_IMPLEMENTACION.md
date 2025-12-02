# Semana 6 - Implementación del Agente RAG

Este documento describe la implementación completa del Agente RAG según los criterios de evaluación.

## Componentes Implementados

### 1. Grafo Lineal en LangGraph ✅

**Archivo**: `app/flows/rag_agent.py`

- **Estado del Agente**: `AgentState` con campo `messages` usando reducer `add_messages`
- **Nodos**:
  - `ask`: Invoca la herramienta MCP para consultar el RAG
  - `llm`: Genera la respuesta usando el contexto del RAG
- **Edges (Flujo Lineal)**:
  - `START → ask → llm → END`
- **Compilación**: Grafo compilado con `graph.compile()`

### 2. Conexión MCP y Herramienta RAG ✅

**Archivo**: `app/mcp_server/rag_server.py`

- **Servidor MCP**: Implementado con `FastMCP("rag-server")`
- **Herramienta `ask()`**:
  - Decorada con `@mcp.tool()`
  - Conecta al RAG externo vía HTTP POST
  - Endpoint: `{RAG_BASE_URL}/api/v1/ask`
  - Parámetros: `question`, `top_k`, `collection`, `use_reranking`, `use_query_rewriting`
  - Retorna: Campo `answer` de la respuesta JSON

**Schema de la Herramienta MCP**:
```python
@mcp.tool()
async def ask(query: str) -> str:
    """
    Consulta el sistema RAG externo para recuperar contexto relevante.
    
    Args:
        query (str): La pregunta del usuario que se enviará al sistema RAG
    
    Returns:
        str: El contexto recuperado del RAG (campo 'answer' de la respuesta)
    """
```

### 3. Integración del RAG como Herramienta ✅

**Archivo**: `app/services/rag_agent_service.py`

- **Inicialización MCP**: 
  - Crea sesión MCP usando `stdio_client`
  - Carga herramientas con `load_tools()`
  - Verifica existencia de herramienta `ask`
- **Construcción del Agente**:
  - Llama a `build_rag_agent(llm, ask_tool)`
  - El tool MCP se pasa directamente al grafo

**Archivo**: `app/flows/rag_agent.py`

- **Nodo `ask_node`**:
  - Invoca `ask_tool.ainvoke({"query": question})`
  - Crea `ToolMessage` con el contexto recuperado
  - Maneja errores apropiadamente

### 4. Configuración LangGraph Studio/Deployment ✅

**Archivo**: `app/langgraph.json`
```json
{
  "dependencies": ["./"],
  "graphs": {
    "agent": "./flows/rag_agent.py:graph"
  },
  "env": ".env"
}
```

**Función `graph()`**: `app/flows/rag_agent.py`
- Compatible con LangGraph Studio
- Usa mock tool para visualización
- En producción, MCP se inicializa correctamente vía servicio

### 5. Visualización del Grafo ✅

**Función**: `visualize_graph()` en `app/flows/rag_agent.py`
- Genera imagen PNG usando `get_graph().draw_mermaid_png()`
- Guarda en `app/images/rag_agent_graph.png`

**Script**: `app/scripts/visualize_rag_graph.py`
- Ejecutable independiente para generar visualización
- Uso: `python scripts/visualize_rag_graph.py`

## Flujo de Ejecución

1. **Usuario** → POST `/ask_rag` con `{"question": "..."}`
2. **Router** → `rag_agent_router.py` recibe la petición
3. **Service** → `rag_agent_service.py.ask_rag()`:
   - Inicializa MCP si es necesario
   - Crea `HumanMessage` con la pregunta
   - Invoca el agente: `agent.ainvoke({"messages": [human_message]})`
4. **Grafo** → `rag_agent.py`:
   - **Nodo `ask`**: Invoca herramienta MCP `ask()` → Consulta RAG externo
   - **Nodo `llm`**: Genera respuesta usando contexto del RAG
5. **Response** → Extrae último mensaje (AIMessage) y retorna contenido

## Archivos Clave

| Archivo | Responsabilidad |
|---------|----------------|
| `app/flows/rag_agent.py` | Definición del grafo LangGraph |
| `app/mcp_server/rag_server.py` | Servidor MCP con herramienta `ask()` |
| `app/services/rag_agent_service.py` | Servicio que gestiona ciclo de vida del agente |
| `app/routers/rag_agent_router.py` | Endpoint HTTP `/ask_rag` |
| `app/langgraph.json` | Configuración para LangGraph Studio/Deployment |
| `app/mcp_server/config.py` | Configuración de servidores MCP |
| `app/mcp_server/tools.py` | Cargador de herramientas MCP |

## Verificación de Criterios

### ✅ Criterio 1: Implementación (1.0 punto)
- [x] Grafo funcional en LangGraph con flujo lineal correctamente definido
- [x] Conexión MCP configurada apropiadamente
- [x] RAG integrado como herramienta (tool) con schema correspondiente
- [x] El agente formatea la respuesta del RAG (usa contexto directamente)

### 📝 Criterio 2: Video Demostrativo (1.0 punto)
- [ ] Video de máximo 2 minutos
- [ ] Evidencia: frontend operativo, consulta al agente, invocación al RAG vía MCP, respuesta formateada
- [ ] Enlazado en wiki bajo "Semana 6"

### 📝 Criterio 3: Trazas de LangSmith (1.0 punto)
- [ ] Traza exportada que visualiza flujo del agente lineal
- [ ] Muestra invocación de herramientas y estados del grafo
- [ ] Enlace funcional y accesible en wiki bajo "Semana 6"

## Comandos Útiles

### Visualizar el grafo
```bash
cd app
python scripts/visualize_rag_graph.py
```

### Ejecutar con LangGraph Studio
```bash
langgraph dev
```

### Probar el endpoint
```bash
curl -X POST "http://localhost:8000/ask_rag" \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Qué información tienes?"}'
```

## Notas Técnicas

1. **MCP stdio**: El servidor MCP se comunica vía stdio, por lo que el logging debe usar `stderr` para no interferir
2. **Mock Tool**: La función `graph()` usa un mock tool para compatibilidad con LangGraph Studio
3. **Inicialización Lazy**: MCP se inicializa solo cuando se necesita (primera consulta)
4. **Manejo de Errores**: Todos los componentes manejan errores apropiadamente y retornan mensajes informativos

