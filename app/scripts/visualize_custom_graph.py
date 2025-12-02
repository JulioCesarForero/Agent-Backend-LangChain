"""
Script para visualizar el grafo del Agente Custom (ReAct)
==========================================================

Este script genera una visualización del grafo del Agente Custom usando LangGraph.
La imagen se guarda en app/images/custom_agent_graph.png

OPCIONES DE USO:

1. Dentro del contenedor Docker (RECOMENDADO):
   docker exec -it app python scripts/visualize_custom_graph.py

2. Localmente (requiere instalar dependencias):
   pip install -r requirements.txt
   python scripts/visualize_custom_graph.py
"""

import sys
from pathlib import Path

# Agregar el directorio app al path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

# Verificar que las dependencias estén instaladas
try:
    import langgraph
    import langchain_core
except ImportError as e:
    print("\n" + "="*60)
    print("ERROR: Dependencias no instaladas")
    print("="*60)
    print("\nPara ejecutar este script, tienes dos opciones:\n")
    print("OPCIÓN 1: Ejecutar dentro del contenedor Docker (RECOMENDADO)")
    print("  docker exec -it app python scripts/visualize_custom_graph.py\n")
    print("OPCIÓN 2: Instalar dependencias localmente")
    print("  pip install -r requirements.txt")
    print("  python scripts/visualize_custom_graph.py\n")
    print("="*60)
    sys.exit(1)

from flows.custom_agent import visualize_graph
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Verificar que GOOGLE_API_KEY esté configurado
    if not os.getenv("GOOGLE_API_KEY"):
        print("\n" + "="*60)
        print("ADVERTENCIA: GOOGLE_API_KEY no está configurado")
        print("="*60)
        print("\nEl script puede fallar si la API key no está configurada.")
        print("Asegúrate de tener GOOGLE_API_KEY en tu archivo .env o variables de entorno.\n")
        print("="*60)
    
    logger.info("Generando visualización del grafo Custom Agent...")
    
    try:
        output_path = visualize_graph()
        
        if output_path:
            logger.info(f"✓ Visualización generada exitosamente: {output_path}")
            print(f"\n✓ Grafo visualizado y guardado en: {output_path}")
            print(f"  Puedes abrir la imagen en: {Path(output_path).absolute()}")
        else:
            logger.error("✗ No se pudo generar la visualización del grafo")
            print("\n✗ Error: No se pudo generar la visualización del grafo")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error al generar visualización: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        print("\nSugerencia: Asegúrate de que el contenedor Docker esté corriendo:")
        print("  docker-compose up -d")
        print("  docker exec -it app python scripts/visualize_custom_graph.py")
        sys.exit(1)

