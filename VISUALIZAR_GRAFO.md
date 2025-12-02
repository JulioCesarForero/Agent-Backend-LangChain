# Cómo Visualizar el Grafo del Agente RAG

Este documento explica cómo generar la visualización del grafo del Agente RAG.

## Opción 1: Ejecutar dentro del contenedor Docker (RECOMENDADO)

Si ya tienes el contenedor corriendo:

```bash
docker exec -it app python scripts/visualize_rag_graph.py
```

Si el contenedor no está corriendo:

```bash
# Levantar el contenedor
docker-compose up -d

# Ejecutar el script de visualización
docker exec -it app python scripts/visualize_rag_graph.py
```

La imagen se guardará en: `app/images/rag_agent_graph.png`

## Opción 2: Ejecutar localmente

Si prefieres ejecutar el script en tu máquina local:

```bash
# 1. Instalar dependencias (si no las tienes)
pip install -r app/requirements.txt

# 2. Ejecutar el script
cd app
python scripts/visualize_rag_graph.py
```

## Opción 3: Usar LangGraph Studio

Para una visualización interactiva:

```bash
# Asegúrate de estar en el directorio app
cd app

# Instalar LangGraph CLI si no lo tienes
pip install langgraph-cli

# Ejecutar LangGraph Studio
langgraph dev
```

Esto abrirá una interfaz web donde podrás:
- Ver el grafo visualmente
- Probar el agente interactivamente
- Ver las trazas de ejecución

## Verificar que funcionó

Después de ejecutar el script, deberías ver:

```
✓ Grafo visualizado y guardado en: app/images/rag_agent_graph.png
```

Y el archivo debería existir en esa ubicación.

## Solución de Problemas

### Error: "No module named 'langgraph'"

**Solución**: Ejecuta el script dentro del contenedor Docker:
```bash
docker exec -it app python scripts/visualize_rag_graph.py
```

### Error: "No se pudo visualizar el grafo"

**Posibles causas**:
1. Faltan dependencias de visualización (pygraphviz, etc.)
2. El contenedor no está corriendo

**Solución**: 
```bash
# Verificar que el contenedor esté corriendo
docker ps

# Si no está corriendo, levantarlo
docker-compose up -d

# Intentar de nuevo
docker exec -it app python scripts/visualize_rag_graph.py
```

### El archivo se genera pero está vacío o corrupto

**Solución**: Verifica que las dependencias de visualización estén instaladas en el contenedor:
```bash
docker exec -it app pip list | grep -i graph
```

