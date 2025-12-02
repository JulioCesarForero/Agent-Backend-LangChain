"""
Script para probar las herramientas MCP de GreenTravelBackend
==============================================================

Este script prueba las herramientas del servidor MCP de los servicios de
Liquidaciones y Proveedores de GreenTravelBackend de manera independiente,
sin necesidad de ejecutar el agente completo.

OPCIONES DE USO:

1. Dentro del contenedor Docker (RECOMENDADO):
   docker exec -it app python scripts/test_greentravel_tools.py

2. Localmente (requiere instalar dependencias):
   pip install -r requirements.txt
   python scripts/test_greentravel_tools.py

CONFIGURACIÓN:

El script detecta automáticamente la configuración según las variables de entorno:

1. Si GREENTRAVEL_GATEWAY_URL está configurada (NGINX Gateway):
   - Usa esa URL base para acceder a través del gateway
   - Ejemplo: GREENTRAVEL_GATEWAY_URL=http://34.134.74.83 (GCP)
   - Ejemplo: GREENTRAVEL_GATEWAY_URL=http://localhost (desarrollo local)

2. Si no está configurada (conexión directa):
   - Liquidaciones: puerto 8001 (o configura LIQUIDACIONES_SERVICE_URL)
   - Proveedores: puerto 8002 (o configura PROVEDORES_SERVICE_URL)
   - Detecta automáticamente si está en Docker y usa host.docker.internal
"""

import sys
import asyncio
import json
from pathlib import Path

# Agregar el directorio app al path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

# Verificar que las dependencias estén instaladas
try:
    import httpx
    from mcp.client.stdio import stdio_client
    from mcp import ClientSession
    from dotenv import load_dotenv
except ImportError as e:
    print("\n" + "="*60)
    print("ERROR: Dependencias no instaladas")
    print("="*60)
    print("\nPara ejecutar este script, tienes dos opciones:\n")
    print("OPCIÓN 1: Ejecutar dentro del contenedor Docker (RECOMENDADO)")
    print("  docker exec -it app python scripts/test_greentravel_tools.py\n")
    print("OPCIÓN 2: Instalar dependencias localmente")
    print("  pip install -r requirements.txt")
    print("  python scripts/test_greentravel_tools.py\n")
    print("="*60)
    sys.exit(1)

from mcp_server.config import get_greentravel_server_parameters
from mcp_server.tools import load_tools
import logging
import os

# Cargar variables de entorno desde .env
# Buscar el archivo .env en el directorio app (un nivel arriba de scripts)
env_path = app_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[CONFIG] Variables de entorno cargadas desde: {env_path}")
else:
    # Si no existe .env, intentar cargar desde el directorio actual
    load_dotenv()
    print("[CONFIG] Intentando cargar variables de entorno desde directorio actual")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _get_liquidaciones_service_url():
    """
    Obtiene la URL base del servicio de liquidaciones desde GREENTRAVEL_GATEWAY_URL.
    
    La URL base se usa para construir las rutas completas:
    - {base_url}/api/v1/liquidaciones
    
    Configuración:
    - GREENTRAVEL_GATEWAY_URL: URL base del gateway NGINX (ej: http://34.134.74.83)
    - Si no está configurada, usa http://localhost como valor por defecto para desarrollo
    """
    # Obtener URL base del gateway NGINX
    base_url = os.getenv("GREENTRAVEL_GATEWAY_URL", "http://localhost")
    
    # Limpiar la URL (remover trailing slash)
    return base_url.rstrip('/')


def _get_provedores_service_url():
    """
    Obtiene la URL base del servicio de proveedores desde GREENTRAVEL_GATEWAY_URL.
    
    La URL base se usa para construir las rutas completas:
    - {base_url}/api/v1/provedores
    
    Configuración:
    - GREENTRAVEL_GATEWAY_URL: URL base del gateway NGINX (ej: http://34.134.74.83)
    - Si no está configurada, usa http://localhost como valor por defecto para desarrollo
    """
    # Obtener URL base del gateway NGINX (misma que liquidaciones)
    base_url = os.getenv("GREENTRAVEL_GATEWAY_URL", "http://localhost")
    
    # Limpiar la URL (remover trailing slash)
    return base_url.rstrip('/')


async def test_service_connection(service_name: str, service_url_getter, port: int, env_var: str):
    """Verifica que un servicio esté accesible."""
    service_url = service_url_getter()
    
    # Detectar si se está usando NGINX gateway
    # Verificar si GREENTRAVEL_GATEWAY_URL está configurada (no None y no vacía)
    gateway_url = os.getenv("GREENTRAVEL_GATEWAY_URL")
    is_nginx_gateway = gateway_url is not None and gateway_url.strip() != ""
    
    if is_nginx_gateway:
        # Cuando se usa NGINX, el health check es a través del gateway
        # NGINX tiene un endpoint /health que hace proxy al servicio de liquidaciones
        health_url = f"{service_url.rstrip('/')}/health"
    else:
        # Sin NGINX, usar el health check directo del servicio
        health_url = f"{service_url.rstrip('/')}/health"
    
    print(f"\n{'='*60}")
    print(f"Verificando conexión al Servicio de {service_name}...")
    print(f"{'='*60}")
    print(f"Service URL: {service_url}")
    print(f"Health Check: {health_url}")
    if is_nginx_gateway:
        print(f"Modo: NGINX Gateway (GREENTRAVEL_GATEWAY_URL configurado)")
    else:
        print(f"Modo: Conexión directa (puerto {port})")
    
    # También intentar con localhost si estamos en Docker y falla con host.docker.internal
    urls_to_try = [health_url]
    if not is_nginx_gateway and "host.docker.internal" in service_url:
        # También intentar con el nombre del contenedor si están en la misma red
        service_container_name = f"{service_name.lower()}-service"
        urls_to_try.append(f"http://{service_container_name}:{port}/health")
        urls_to_try.append(f"http://localhost:{port}/health")
    
    for url in urls_to_try:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    print(f"✓ Servicio accesible en: {url}")
                    # Actualizar la URL del servicio si encontramos una que funciona
                    if url != health_url:
                        os.environ[env_var] = url.replace("/health", "")
                    return True
        except Exception as e:
            if url == urls_to_try[-1]:  # Último intento
                print(f"✗ Error conectando al servicio: {e}")
                print(f"  Intentado: {', '.join(urls_to_try)}")
                print(f"\nSugerencias:")
                if is_nginx_gateway:
                    print(f"  1. Verifica que NGINX Gateway esté corriendo y accesible:")
                    print(f"     curl {health_url}")
                    print(f"  2. Si estás en GCP, verifica que GREENTRAVEL_GATEWAY_URL sea correcta:")
                    print(f"     GREENTRAVEL_GATEWAY_URL=http://34.134.74.83")
                    print(f"  3. Si estás en desarrollo local con NGINX:")
                    print(f"     GREENTRAVEL_GATEWAY_URL=http://localhost")
                else:
                    print(f"  1. Asegúrate de que el servicio de {service_name.lower()} esté corriendo:")
                    print(f"     cd GreenTravelBackend")
                    print(f"     docker-compose up -d {service_name.lower()}-service")
                    print(f"  2. Verifica que el servicio responda:")
                    print(f"     curl http://localhost:{port}/health")
                    print(f"  3. Si estás en Docker, configura {env_var}:")
                    print(f"     - Para host: http://host.docker.internal:{port}")
                    print(f"  4. O configura GREENTRAVEL_GATEWAY_URL para usar NGINX:")
                    print(f"     GREENTRAVEL_GATEWAY_URL=http://localhost (o IP del servidor)")
                return False
            continue
    
    return False


async def test_mcp_server():
    """Prueba la conexión al servidor MCP y carga las herramientas."""
    print(f"\n{'='*60}")
    print("2. Inicializando servidor MCP...")
    print(f"{'='*60}")
    
    try:
        server_params = get_greentravel_server_parameters()
        stdio_ctx = stdio_client(server_params)
        read, write = await stdio_ctx.__aenter__()
        session = await ClientSession(read, write).__aenter__()
        await session.initialize()
        
        print("✓ Servidor MCP inicializado")
        
        # Cargar herramientas
        tools, tools_by_name = await load_tools(session)
        print(f"✓ {len(tools)} herramientas cargadas")
        
        # Listar herramientas disponibles
        print("\nHerramientas disponibles:")
        for tool_name in sorted(tools_by_name.keys()):
            print(f"  - {tool_name}")
        
        return session, tools_by_name, stdio_ctx
        
    except Exception as e:
        print(f"✗ Error inicializando servidor MCP: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


async def test_tool(session, tool_name, *args, **kwargs):
    """Ejecuta una herramienta MCP y muestra el resultado."""
    try:
        # Obtener la herramienta
        tool_call = {
            "name": tool_name,
            "arguments": kwargs if kwargs else {}
        }
        
        # Ejecutar la herramienta
        result = await session.call_tool(tool_name, kwargs)
        
        # Mostrar resultado
        if result.content:
            content = result.content[0] if result.content else None
            if content and hasattr(content, 'text'):
                try:
                    result_json = json.loads(content.text)
                    print(f"✓ {tool_name}: {json.dumps(result_json, ensure_ascii=False, indent=2)[:200]}...")
                except:
                    print(f"✓ {tool_name}: {content.text[:200]}...")
            else:
                print(f"✓ {tool_name}: {str(result)[:200]}...")
        else:
            print(f"✓ {tool_name}: Sin contenido")
        
        return True
        
    except Exception as e:
        print(f"✗ {tool_name}: Error - {str(e)}")
        return False


async def run_tests():
    """Ejecuta todas las pruebas."""
    print("\n" + "="*60)
    print("SCRIPT DE PRUEBA - HERRAMIENTAS MCP GREEN TRAVEL BACKEND")
    print("="*60)
    
    # Verificar variables de entorno
    greentravel_gateway = os.getenv("GREENTRAVEL_GATEWAY_URL")
    liquidaciones_url = _get_liquidaciones_service_url()
    provedores_url = _get_provedores_service_url()
    
    print(f"\nConfiguración de URLs:")
    if greentravel_gateway and greentravel_gateway.strip():
        print(f"GREENTRAVEL_GATEWAY_URL: {greentravel_gateway} (NGINX Gateway)")
        print(f"  → Liquidaciones: {liquidaciones_url}/api/v1/liquidaciones")
        print(f"  → Proveedores: {provedores_url}/api/v1/provedores")
    else:
        print(f"GREENTRAVEL_GATEWAY_URL: No configurado (usando valor por defecto: http://localhost)")
        print(f"  → Liquidaciones: {liquidaciones_url}/api/v1/liquidaciones")
        print(f"  → Proveedores: {provedores_url}/api/v1/provedores")
        print(f"\n  NOTA: Para usar el gateway NGINX en GCP, configura en .env:")
        print(f"        GREENTRAVEL_GATEWAY_URL=http://34.134.74.83")
    
    # 1. Verificar conexión a los servicios
    liquidaciones_ok = await test_service_connection(
        "Liquidaciones", _get_liquidaciones_service_url, 8001, "LIQUIDACIONES_SERVICE_URL"
    )
    provedores_ok = await test_service_connection(
        "Proveedores", _get_provedores_service_url, 8002, "PROVEDORES_SERVICE_URL"
    )
    
    if not liquidaciones_ok and not provedores_ok:
        print("\n✗ No se puede continuar sin conexión a ningún servicio")
        return
    
    # 2. Inicializar servidor MCP
    session, tools_by_name, stdio_ctx = await test_mcp_server()
    if not session:
        print("\n✗ No se puede continuar sin servidor MCP")
        return
    
    # 3. Probar herramientas básicas
    print(f"\n{'='*60}")
    print("3. Probando herramientas básicas...")
    print(f"{'='*60}")
    
    tests_passed = 0
    tests_failed = 0
    
    # Pruebas de Liquidaciones
    if liquidaciones_ok:
        print("\n--- PRUEBAS DE LIQUIDACIONES ---")
        # Test: Estadísticas de liquidaciones
        print("\n[Test 1] Estadísticas de liquidaciones...")
        if await test_tool(session, "get_liquidacion_stats"):
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Test: Listar liquidaciones (primera página)
        print("\n[Test 2] Listar liquidaciones (página 1)...")
        if await test_tool(session, "list_liquidaciones", page=1, limit=5):
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        print("\n--- PRUEBAS DE LIQUIDACIONES (SALTADAS - servicio no disponible) ---")
    
    # Pruebas de Proveedores
    if provedores_ok:
        print("\n--- PRUEBAS DE PROVEEDORES ---")
        # Test: Estadísticas de proveedores
        print("\n[Test 3] Estadísticas de proveedores...")
        if await test_tool(session, "get_provedor_stats"):
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Test: Listar proveedores (primera página)
        print("\n[Test 4] Listar proveedores (página 1)...")
        if await test_tool(session, "list_provedores", page=1, limit=5):
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        print("\n--- PRUEBAS DE PROVEEDORES (SALTADAS - servicio no disponible) ---")
    
    # Cerrar sesión
    if stdio_ctx:
        await session.__aexit__(None, None, None)
        await stdio_ctx.__aexit__(None, None, None)
    
    # Resumen
    print(f"\n{'='*60}")
    print("RESUMEN DE PRUEBAS")
    print(f"{'='*60}")
    print(f"✓ Pruebas exitosas: {tests_passed}")
    print(f"✗ Pruebas fallidas: {tests_failed}")
    print(f"Total: {tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("\n✓ Todas las pruebas pasaron exitosamente!")
    else:
        print(f"\n⚠ {tests_failed} prueba(s) fallaron. Revisa los errores arriba.")
    
    print(f"\n{'='*60}")


if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\nPrueba interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

