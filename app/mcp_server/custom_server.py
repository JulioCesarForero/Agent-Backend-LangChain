"""
Servidor MCP para el Agente Especializado
==========================================

Este módulo implementa el servidor MCP que expone múltiples herramientas
personalizadas para el Agente Especializado, incluyendo integración con
GreenTravel microservices (Liquidaciones, Proveedores) y extracción de datos
de facturas desde RAG.
"""

from mcp.server.fastmcp import FastMCP
import logging
import json
from datetime import datetime, timedelta
import httpx
import os
import sys
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Configurar logging con UTF-8 primero (antes de cargar .env para poder loguear)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr)  # stderr para no interferir con MCP stdio
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

# Cargar variables de entorno desde .env
# Buscar el archivo .env en el directorio app (un nivel arriba de mcp_server)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"[CONFIG] Variables de entorno cargadas desde: {env_path}")
else:
    # Si no existe .env, intentar cargar desde el directorio actual
    load_dotenv()
    logger.info("[CONFIG] Intentando cargar variables de entorno desde directorio actual")

mcp = FastMCP("custom-server")

# Configuración del Servicio de Liquidaciones
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
    base_url = base_url.rstrip('/')
    
    logger.info(f"[LIQUIDACIONES] GREENTRAVEL_GATEWAY_URL={os.getenv('GREENTRAVEL_GATEWAY_URL', 'NO CONFIGURADO')}")
    logger.info(f"[LIQUIDACIONES] URL base configurada: {base_url}")
    return base_url

# Configuración del Servicio de Proveedores
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
    base_url = base_url.rstrip('/')
    
    logger.info(f"[PROVEDORES] GREENTRAVEL_GATEWAY_URL={os.getenv('GREENTRAVEL_GATEWAY_URL', 'NO CONFIGURADO')}")
    logger.info(f"[PROVEDORES] URL base configurada: {base_url}")
    return base_url

# URLs de servicios GreenTravel
LIQUIDACIONES_SERVICE_URL = _get_liquidaciones_service_url()
logger.info(f"[LIQUIDACIONES] URL final: {LIQUIDACIONES_SERVICE_URL}/api/v1/liquidaciones")

PROVEDORES_SERVICE_URL = _get_provedores_service_url()
logger.info(f"[PROVEDORES] URL final: {PROVEDORES_SERVICE_URL}/api/v1/provedores")

RAG_BASE_URL = os.getenv("RAG_BASE_URL", "http://34.63.203.124")

HTTP_TIMEOUT = 30.0

# ===============================================================================
# FUNCIONES AUXILIARES
# ===============================================================================

async def _make_request(method: str, url: str, **kwargs) -> dict:
    """
    Realiza una petición HTTP a los servicios de GreenTravelBackend y retorna la respuesta como dict.
    
    Args:
        method: Método HTTP (GET, POST, PUT, DELETE)
        url: URL completa del endpoint
        **kwargs: Argumentos adicionales para httpx (json, params, etc.)
    
    Returns:
        dict: Respuesta JSON parseada
    
    Raises:
        ValueError: Si hay un error en la petición HTTP
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.request(method, url, **kwargs)
            
            # Para DELETE, puede retornar 204 No Content
            if response.status_code == 204:
                return {"success": True, "message": "Operación completada exitosamente"}
            
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        error_msg = f"Error HTTP {e.response.status_code}: {e.response.text}"
        logger.error(f"{method} {url}: {error_msg}")
        raise ValueError(error_msg)
    except httpx.TimeoutException as e:
        error_msg = f"Timeout al conectar con el servicio: {str(e)}"
        logger.error(f"{method} {url}: {error_msg}")
        raise ValueError(error_msg)
    except httpx.RequestError as e:
        error_msg = f"Error de conexión: {str(e)}"
        logger.error(f"{method} {url}: {error_msg}")
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        logger.error(f"{method} {url}: {error_msg}")
        raise ValueError(error_msg)



# ===============================================================================
# HERRAMIENTA MCP 1 - CALCULAR VENCIMIENTO DE FACTURA
# ===============================================================================

@mcp.tool()
async def calcular_vencimiento(fecha_emision: str, dias_credito: int) -> str:
    """
    Calcula la fecha de vencimiento de una factura y determina si ya está vencida.

    Args:
        fecha_emision (str): Fecha de emisión en formato YYYY-MM-DD (formato preferido).
                            También acepta DD-MM-YYYY, DD/MM/YYYY, pero se recomienda YYYY-MM-DD.
        dias_credito (int): Días de crédito otorgado al cliente.

    Returns:
        dict: Diccionario con:
            - fecha_emision: Fecha de emisión en formato YYYY-MM-DD
            - fecha_vencimiento: Fecha de vencimiento en formato YYYY-MM-DD
            - vencida (bool): Indica si la factura ya está vencida
            - dias_restantes: Días restantes hasta el vencimiento (negativo si ya venció)
            - mensaje: Mensaje descriptivo del estado
            - error (si aplica): Mensaje de error si hubo algún problema
    """
    try:
        fecha_emision_dt = None
        
        # Intentar diferentes formatos de fecha
        formatos_fecha = [
            "%Y-%m-%d",      # YYYY-MM-DD (formato preferido)
            "%d-%m-%Y",      # DD-MM-YYYY
            "%d/%m/%Y",      # DD/MM/YYYY
            "%Y/%m/%d",      # YYYY/MM/DD
        ]
        
        for formato in formatos_fecha:
            try:
                fecha_emision_dt = datetime.strptime(fecha_emision.strip(), formato).date()
                break
            except ValueError:
                continue
        
        if fecha_emision_dt is None:
            raise ValueError(f"No se pudo parsear la fecha '{fecha_emision}'. Use formato YYYY-MM-DD (ej: 2025-10-03)")

        dias_credito = int(dias_credito)
        fecha_vencimiento = fecha_emision_dt + timedelta(days=dias_credito)
        hoy = datetime.now().date()

        dias_restantes = (fecha_vencimiento - hoy).days
        vencida = dias_restantes < 0

        mensaje = (
            f"La factura venció hace {-dias_restantes} días." if vencida
            else f"Faltan {dias_restantes} días para el vencimiento."
        )

        result = {
            "fecha_emision": fecha_emision_dt.strftime("%Y-%m-%d"),  # Siempre retornar en formato YYYY-MM-DD
            "fecha_vencimiento": fecha_vencimiento.strftime("%Y-%m-%d"),  # Siempre retornar en formato YYYY-MM-DD
            "vencida": vencida,
            "dias_restantes": dias_restantes,
            "mensaje": mensaje,
            "error": None
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Error calculando vencimiento: {e}")
        error_result = {
            "fecha_emision": fecha_emision,
            "fecha_vencimiento": None,
            "vencida": None,
            "dias_restantes": None,
            "mensaje": f"Hubo un error al intentar calcular la fecha de vencimiento: {e}",
            "error": str(e)
        }
        return json.dumps(error_result, ensure_ascii=False, indent=2)

# ===============================================================================
# HERRAMIENTA MCP 2 - OBTENER DATOS DE FACTURA DESDE RAG
# ===============================================================================

@mcp.tool()
async def rag_get_invoice_data(invoice_number: Optional[str] = None, cufe: Optional[str] = None, provider_nit: Optional[str] = None) -> str:
    """
    Obtiene información completa de una factura desde el sistema RAG.
    
    **USA ESTA HERRAMIENTA SIEMPRE que el usuario pregunte sobre facturas, mencione un número de factura, CUFE, o NIT de proveedor relacionado con facturas.**
    
    Esta es la ÚNICA forma de obtener información de facturas. NO intentes responder sobre facturas sin usar esta herramienta primero.
    
    Ejemplos de cuándo usar:
    - Usuario pregunta "Dame información de la factura HBE122090" → usa invoice_number="HBE122090"
    - Usuario pregunta "¿Qué facturas hay?" → llama sin parámetros
    - Usuario pregunta "Muéstrame la factura del proveedor con NIT 900123456" → usa provider_nit="900123456"
    - Usuario menciona un número de factura (HBE122090, E018-175709, etc.) → extrae el número y úsalo como invoice_number
    
    Args:
        invoice_number: Número de factura a buscar (ej: HBE122090, E018-175709, FACT-12345). 
                        Extrae este número de la pregunta del usuario si menciona una factura específica.
        cufe: CUFE de la factura (32 caracteres alfanuméricos). Usa si el usuario proporciona un CUFE.
        provider_nit: NIT del proveedor. Usa si el usuario pregunta por facturas de un proveedor específico.
        
    Returns:
        str: Texto completo de la factura obtenido del RAG con todos los detalles (número, CUFE, proveedor, cliente, fecha, total, items, etc.)
    """
    # Construir query para RAG
    query_parts = []
    if invoice_number:
        query_parts.append(f"factura número {invoice_number}")
    if cufe:
        query_parts.append(f"CUFE {cufe}")
    if provider_nit:
        query_parts.append(f"proveedor NIT {provider_nit}")
    
    if not query_parts:
        query = "Dame toda la información de la factura"
    else:
        query = f"Dame toda la información de la factura con {' y '.join(query_parts)}"
    
    rag_url = f"{RAG_BASE_URL.rstrip('/')}/api/v1/ask"
    
    # Configuración del RAG (mismos valores que rag_server.py)
    rag_collection = "semana3_test_collection"
    rag_top_k = 5
    rag_use_reranking = True
    rag_use_query_rewriting = True
    
    payload = {
        "question": query,
        "top_k": rag_top_k,
        "collection": rag_collection,
        "use_reranking": rag_use_reranking,
        "use_query_rewriting": rag_use_query_rewriting
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(rag_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if "answer" not in result:
                return "Error: La respuesta del RAG no contiene el campo 'answer'"
            
            invoice_text = result["answer"]
            logger.info(f"[RAG_GET_INVOICE_DATA] Texto obtenido del RAG ({len(invoice_text)} caracteres)")
            
            # Retornar el texto directamente - el agente lo interpretará cuando sea necesario
            return invoice_text
                
    except httpx.HTTPError as e:
        logger.error(f"Error HTTP consultando RAG: {e}")
        return f"Error HTTP consultando RAG: {str(e)}"
    except Exception as e:
        logger.error(f"Error obteniendo datos de factura desde RAG: {e}")
        return f"Error obteniendo datos de factura: {str(e)}"


# ===============================================================================
# HERRAMIENTAS MCP - LIQUIDACIONES
# ===============================================================================

@mcp.tool()
async def list_liquidaciones(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    estado: Optional[int] = None,
    id_reserva: Optional[int] = None,
    factura: Optional[int] = None
) -> str:
    """
    Lista liquidaciones con paginación y filtros opcionales.
    
    Args:
        page: Número de página (inicia en 1, default: 1)
        limit: Elementos por página (1-100, default: 50)
        search: Término de búsqueda en nombre empresa, pasajero, asesor (opcional)
        estado: Filtrar por estado (1=activo, 0=inactivo, opcional)
        id_reserva: Filtrar por ID de reserva (opcional)
        factura: Filtrar por número de factura (opcional)
    
    Returns:
        str: JSON string con lista paginada de liquidaciones
    """
    url = f"{LIQUIDACIONES_SERVICE_URL.rstrip('/')}/api/v1/liquidaciones"
    params = {
        "page": page,
        "limit": limit
    }
    
    if search:
        params["search"] = search
    if estado is not None:
        params["estado"] = estado
    if id_reserva is not None:
        params["id_reserva"] = id_reserva
    if factura is not None:
        params["factura"] = factura
    
    try:
        result = await _make_request("GET", url, params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_liquidacion(liquidacion_id: int) -> str:
    """
    Obtiene una liquidación específica por su ID.
    
    Args:
        liquidacion_id: ID único de la liquidación
    
    Returns:
        str: JSON string con los datos de la liquidación
    """
    url = f"{LIQUIDACIONES_SERVICE_URL.rstrip('/')}/api/v1/liquidaciones/{liquidacion_id}"
    
    try:
        result = await _make_request("GET", url)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def create_liquidacion(data: str) -> str:
    """
    Crea una nueva liquidación.
    
    Args:
        data: JSON string con los datos de la liquidación.
              Debe incluir al menos 'observaciones' (requerido).
              Campos opcionales: id_reserva, nombre_asesor, nombre_empresa, nit_empresa,
              direccion_empresa, telefono_empresa, servicio, fecha_servicio, incluye_servicio,
              numero_pasajeros, valor_liquidacion, iva, valor_iva, valor_total_iva,
              nombre_pasajero, fecha, factura, estado, origen_venta
    
    Returns:
        str: JSON string con la liquidación creada
    """
    url = f"{LIQUIDACIONES_SERVICE_URL.rstrip('/')}/api/v1/liquidaciones"
    
    try:
        payload = json.loads(data)
        result = await _make_request("POST", url, json=payload)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"JSON inválido: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def update_liquidacion(liquidacion_id: int, data: str) -> str:
    """
    Actualiza una liquidación existente.
    
    Args:
        liquidacion_id: ID único de la liquidación a actualizar
        data: JSON string con los campos a actualizar (todos opcionales)
    
    Returns:
        str: JSON string con la liquidación actualizada
    """
    url = f"{LIQUIDACIONES_SERVICE_URL.rstrip('/')}/api/v1/liquidaciones/{liquidacion_id}"
    
    try:
        payload = json.loads(data)
        result = await _make_request("PUT", url, json=payload)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"JSON inválido: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def delete_liquidacion(liquidacion_id: int) -> str:
    """
    Elimina una liquidación (soft delete - marca como inactiva).
    
    Args:
        liquidacion_id: ID único de la liquidación a eliminar
    
    Returns:
        str: JSON string confirmando la eliminación
    """
    url = f"{LIQUIDACIONES_SERVICE_URL.rstrip('/')}/api/v1/liquidaciones/{liquidacion_id}"
    
    try:
        result = await _make_request("DELETE", url)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_liquidacion_stats() -> str:
    """
    Obtiene estadísticas agregadas sobre las liquidaciones.
    
    Returns:
        str: JSON string con estadísticas (total, activas, inactivas, por_estado)
    """
    url = f"{LIQUIDACIONES_SERVICE_URL.rstrip('/')}/api/v1/liquidaciones/stats"
    
    try:
        result = await _make_request("GET", url)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ===============================================================================
# HERRAMIENTAS MCP - PROVEEDORES
# ===============================================================================

@mcp.tool()
async def list_provedores(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    estado: Optional[int] = None,
    tipo: Optional[int] = None,
    ciudad: Optional[int] = None
) -> str:
    """
    Lista proveedores con paginación y filtros opcionales.
    
    Args:
        page: Número de página (inicia en 1, default: 1)
        limit: Elementos por página (1-100, default: 50)
        search: Término de búsqueda en nombre, razón social, identificación (opcional)
        estado: Filtrar por estado (1=activo, 0=inactivo, opcional)
        tipo: Filtrar por tipo de proveedor (opcional)
        ciudad: Filtrar por ID de ciudad (opcional)
    
    Returns:
        str: JSON string con lista paginada de proveedores
    """
    url = f"{PROVEDORES_SERVICE_URL.rstrip('/')}/api/v1/provedores"
    params = {
        "page": page,
        "limit": limit
    }
    
    if search:
        params["search"] = search
    if estado is not None:
        params["estado"] = estado
    if tipo is not None:
        params["tipo"] = tipo
    if ciudad is not None:
        params["ciudad"] = ciudad
    
    try:
        result = await _make_request("GET", url, params=params)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_provedor(provedor_id: int) -> str:
    """
    Obtiene un proveedor específico por su ID.
    
    Args:
        provedor_id: ID único del proveedor
    
    Returns:
        str: JSON string con los datos del proveedor
    """
    url = f"{PROVEDORES_SERVICE_URL.rstrip('/')}/api/v1/provedores/{provedor_id}"
    
    try:
        result = await _make_request("GET", url)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def create_provedor(data: str) -> str:
    """
    Crea un nuevo proveedor.
    
    Args:
        data: JSON string con los datos del proveedor.
              Todos los campos son opcionales: provedor_hotel_code, provedor_razonsocial,
              provedor_nombre, provedor_identificacion, provedor_direccion, provedor_telefono,
              provedor_tipo, provedor_estado (default: 1), provedor_ciudad, provedor_link_dropbox
    
    Returns:
        str: JSON string con el proveedor creado
    """
    url = f"{PROVEDORES_SERVICE_URL.rstrip('/')}/api/v1/provedores"
    
    try:
        payload = json.loads(data)
        result = await _make_request("POST", url, json=payload)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"JSON inválido: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def update_provedor(provedor_id: int, data: str) -> str:
    """
    Actualiza un proveedor existente.
    
    Args:
        provedor_id: ID único del proveedor a actualizar
        data: JSON string con los campos a actualizar (todos opcionales)
    
    Returns:
        str: JSON string con el proveedor actualizado
    """
    url = f"{PROVEDORES_SERVICE_URL.rstrip('/')}/api/v1/provedores/{provedor_id}"
    
    try:
        payload = json.loads(data)
        result = await _make_request("PUT", url, json=payload)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"JSON inválido: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def delete_provedor(provedor_id: int) -> str:
    """
    Elimina un proveedor (soft delete - marca como inactivo).
    
    Args:
        provedor_id: ID único del proveedor a eliminar
    
    Returns:
        str: JSON string confirmando la eliminación
    """
    url = f"{PROVEDORES_SERVICE_URL.rstrip('/')}/api/v1/provedores/{provedor_id}"
    
    try:
        result = await _make_request("DELETE", url)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_provedor_stats() -> str:
    """
    Obtiene estadísticas agregadas sobre los proveedores.
    
    Returns:
        str: JSON string con estadísticas (total, activos, inactivos, por_estado, por_tipo)
    """
    url = f"{PROVEDORES_SERVICE_URL.rstrip('/')}/api/v1/provedores/stats"
    
    try:
        result = await _make_request("GET", url)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)







# # ===============================================================================
# # HERRAMIENTAS MCP - INTEGRACIÓN PROVEEDORES (Service Port: 8002)
# # ===============================================================================

# @mcp.tool()
# async def get_provedores(search: Optional[str] = None, nit: Optional[str] = None) -> str:
#     """
#     Busca proveedores en el sistema GreenTravel.
    
#     Args:
#         search (str, optional): Término de búsqueda (nombre, razón social, identificación)
#         nit (str, optional): NIT específico para buscar
        
#     Returns:
#         str: JSON string con la lista paginada de proveedores encontrados
#     """
#     params = {}
#     if search:
#         params['search'] = search
#     elif nit:
#         params['search'] = nit  # El API usa 'search' para identificación también
    
#     url = f"{PROVEDORES_URL}/provedores"
    
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.get(url, params=params)
#             response.raise_for_status()
#             return json.dumps(response.json(), ensure_ascii=False)
#     except Exception as e:
#         logger.error(f"Error getting provedores: {e}")
#         return json.dumps({"error": str(e)})

# @mcp.tool()
# async def create_provedor(data: str) -> str:
#     """
#     Crea un nuevo proveedor en el sistema.
    
#     Args:
#         data (str): JSON string con los datos del proveedor.
#                     Debe incluir: provedor_nombre, provedor_identificacion, etc.
    
#     Returns:
#         str: JSON string con la respuesta del servidor (proveedor creado)
#     """
#     url = f"{PROVEDORES_URL}/provedores"
#     try:
#         payload = json.loads(data)
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.post(url, json=payload)
#             if response.status_code not in [200, 201]:
#                 return json.dumps({"error": f"HTTP {response.status_code}: {response.text}"})
#             return json.dumps(response.json(), ensure_ascii=False)
#     except Exception as e:
#         logger.error(f"Error creating provedor: {e}")
#         return json.dumps({"error": str(e)})

# # ===============================================================================
# # HERRAMIENTAS MCP - INTEGRACIÓN FACTURAS (Service Port: 8003)
# # ===============================================================================

# @mcp.tool()
# async def get_invoices(invoice_number: Optional[str] = None, provider_nit: Optional[str] = None) -> str:
#     """
#     Busca facturas en el sistema.
    
#     Args:
#         invoice_number (str, optional): Número de factura
#         provider_nit (str, optional): NIT del proveedor
    
#     Returns:
#         str: JSON string con las facturas encontradas (lista paginada)
#     """
#     params = {}
#     if invoice_number:
#         params['search'] = invoice_number
#     if provider_nit:
#         params['provider_nit'] = provider_nit
    
#     url = f"{FACTURAS_URL}/invoices"
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.get(url, params=params)
#             response.raise_for_status()
#             return json.dumps(response.json(), ensure_ascii=False)
#     except Exception as e:
#         logger.error(f"Error getting invoices: {e}")
#         return json.dumps({"error": str(e)})

# @mcp.tool()
# async def create_invoice(data: str) -> str:
#     """
#     Crea una nueva factura (con o sin items).
    
#     Args:
#         data (str): JSON string con los datos de la factura.
#                     Si contiene 'items', usa el endpoint 'with-items'.
    
#     Returns:
#         str: JSON string con la factura creada
#     """
#     try:
#         payload = json.loads(data)
#         endpoint = "/invoices/with-items" if "items" in payload and payload["items"] else "/invoices"
#         url = f"{FACTURAS_URL}{endpoint}"
        
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.post(url, json=payload)
#             if response.status_code not in [200, 201]:
#                 return json.dumps({"error": f"HTTP {response.status_code}: {response.text}"})
#             return json.dumps(response.json(), ensure_ascii=False)
#     except Exception as e:
#         logger.error(f"Error creating invoice: {e}")
#         return json.dumps({"error": str(e)})

# # ===============================================================================
# # HERRAMIENTAS MCP - INTEGRACIÓN LIQUIDACIONES (Service Port: 8001)
# # ===============================================================================

# @mcp.tool()
# async def get_liquidaciones(search: Optional[str] = None, factura_id: Optional[int] = None) -> str:
#     """
#     Busca liquidaciones existentes.
    
#     Args:
#         search (str, optional): Término de búsqueda
#         factura_id (int, optional): ID de factura asociada
        
#     Returns:
#         str: JSON string con liquidaciones encontradas (lista paginada)
#     """
#     params = {}
#     if search:
#         params['search'] = search
#     if factura_id:
#         params['factura'] = factura_id
    
#     url = f"{LIQUIDACIONES_URL}/liquidaciones"
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.get(url, params=params)
#             response.raise_for_status()
#             return json.dumps(response.json(), ensure_ascii=False)
#     except Exception as e:
#         logger.error(f"Error getting liquidaciones: {e}")
#         return json.dumps({"error": str(e)})

# @mcp.tool()
# async def create_liquidacion(data: str) -> str:
#     """
#     Crea una nueva liquidación.
    
#     Args:
#         data (str): JSON string con datos de la liquidación.
#                     Debe incluir al menos 'observaciones' (requerido).
    
#     Returns:
#         str: JSON string con liquidación creada
#     """
#     url = f"{LIQUIDACIONES_URL}/liquidaciones"
#     try:
#         payload = json.loads(data)
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.post(url, json=payload)
#             if response.status_code not in [200, 201]:
#                 return json.dumps({"error": f"HTTP {response.status_code}: {response.text}"})
#             return json.dumps(response.json(), ensure_ascii=False)
#     except Exception as e:
#         logger.error(f"Error creating liquidacion: {e}")
#         return json.dumps({"error": str(e)})

# # ===============================================================================
# # HERRAMIENTA MCP - MATCHING SERVICES
# # ===============================================================================

# @mcp.tool()
# async def match_services(invoice_items_json: str, service_concepts_json: str) -> str:
#     """
#     Compara items de factura con conceptos de servicios esperados.
    
#     Args:
#         invoice_items_json (str): Lista de items de factura (JSON string)
#         service_concepts_json (str): Lista de servicios esperados/registrados (JSON string)
        
#     Returns:
#         str: JSON string con análisis de coincidencias y discrepancias
#     """
#     try:
#         invoice_items = json.loads(invoice_items_json)
#         services = json.loads(service_concepts_json)
        
#         matches = []
#         discrepancies = []
        
#         # Lógica simple de matching por palabras clave y montos
#         for item in invoice_items:
#             found = False
#             item_desc = item.get('description', '').lower()
#             item_total = float(item.get('total_amount', 0))
            
#             for service in services:
#                 # Asumiendo que 'service' tiene 'nombre' o 'servicio' y 'valor_liquidacion'
#                 service_desc = service.get('nombre', service.get('servicio', '')).lower()
#                 service_val_str = service.get('valor_liquidacion', '0')
#                 # Limpiar string de valor (remover puntos, comas, etc.)
#                 service_val_str = service_val_str.replace('.', '').replace(',', '')
#                 try:
#                     service_val = float(service_val_str)
#                 except:
#                     service_val = 0
                
#                 # Check for description similarity (simple substring)
#                 if service_desc in item_desc or item_desc in service_desc:
#                     # Check amount (tolerancia de 1000 pesos/unidades)
#                     diff = abs(item_total - service_val)
#                     if diff < 1000:
#                         matches.append({
#                             "invoice_item": item,
#                             "service": service,
#                             "confidence": "high",
#                             "reason": "Description and amount match",
#                             "amount_diff": diff
#                         })
#                         found = True
#                         break
#                     else:
#                         discrepancies.append({
#                             "invoice_item": item,
#                             "service": service,
#                             "issue": "Amount mismatch",
#                             "diff": diff,
#                             "invoice_amount": item_total,
#                             "service_amount": service_val
#                         })
            
#             if not found:
#                 discrepancies.append({
#                     "invoice_item": item,
#                     "issue": "No matching service found"
#                 })
                
#         return json.dumps({
#             "matches": matches,
#             "discrepancies": discrepancies,
#             "summary": f"Found {len(matches)} matches and {len(discrepancies)} discrepancies."
#         }, ensure_ascii=False)
        
#     except Exception as e:
#         logger.error(f"Error matching services: {e}")
#         return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run(transport="stdio")

