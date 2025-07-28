from flask import Blueprint, render_template, current_app, jsonify
import folium
import geopandas as gpd
import os
from shapely.geometry import Point
import json
from functools import lru_cache
import logging
import pandas as pd
from pathlib import Path
from utils.data_loader import get_data_directory, load_geojson_with_fallback

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)

@lru_cache(maxsize=128)
def get_population_color(pop_value, region="continental"):
    """Retorna color basado en la densidad de población, escala unificada para todo Ecuador"""
    # Paleta tipo LandScan unificada para todo el territorio ecuatoriano
    if pop_value < 5:
        return "#0066cc", 0.3  # Azul claro - muy baja densidad
    elif pop_value < 25:
        return "#00aa44", 0.4  # Verde - baja densidad
    elif pop_value < 100:
        return "#88dd00", 0.5  # Verde claro - densidad moderada baja
    elif pop_value < 500:
        return "#ffff00", 0.6  # Amarillo - densidad moderada
    elif pop_value < 1500:
        return "#ffaa00", 0.7  # Naranja - densidad alta
    elif pop_value < 5000:
        return "#ff5500", 0.8  # Rojo-naranja - densidad muy alta
    else:
        return "#cc0000", 0.9  # Rojo intenso - densidad extrema

@lru_cache(maxsize=1)
def load_cantones_data():
    """Carga datos de cantones con cache"""
    try:
        return load_geojson_with_fallback("cantones.geojson", "cantones")
    except Exception as e:
        logger.error(f"Error cargando cantones: {e}")
        return None

@lru_cache(maxsize=1)
def load_ecuador_boundaries():
    """Carga fronteras de Ecuador con cache"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "..", "data")
    ecuador_path = os.path.join(DATA_DIR, "ec.json")
    
    try:
        gdf_ecuador = gpd.read_file(ecuador_path)
        return gdf_ecuador, gdf_ecuador.geometry.unary_union
    except Exception as e:
        logger.error(f"Error cargando fronteras: {e}")
        return None, None

@lru_cache(maxsize=1)
def load_all_population_data():
    """Carga TODOS los datos de población REALISTAS para cálculos precisos"""
    try:
        return load_geojson_with_fallback("poblacion_ecuador_realistic.geojson", "población completa")
    except Exception as e:
        logger.error(f"❌ Error cargando datos realistas: {e}")
        return None
    logger.info("🎯 Cargando datos REALISTAS de población...")
    gdf_poblacion = gpd.read_file(poblacion_path)
    
    # Cargar fronteras para filtrado
    gdf_ecuador, ecuador_union = load_ecuador_boundaries()
    if gdf_ecuador is None:
        logger.warning("No se pudieron cargar fronteras de Ecuador")
        return gdf_poblacion  # Usar todos los datos sin filtro espacial
        
    # Asegurar mismo CRS
    if gdf_poblacion.crs != gdf_ecuador.crs:
        gdf_poblacion = gdf_poblacion.to_crs(gdf_ecuador.crs)
    
    # Filtrar espacialmente (SIN LÍMITE DE PUNTOS)
    logger.info("Filtrando puntos dentro de Ecuador...")
    gdf_filtrada = gdf_poblacion[
        gdf_poblacion.within(ecuador_union) | 
        gdf_poblacion.intersects(ecuador_union)
    ]
    
    # Estadísticas de los datos cargados
    total_population = gdf_filtrada['population'].sum()
    logger.info(f"✅ DATOS REALISTAS cargados: {len(gdf_filtrada):,} puntos")
    logger.info(f"🏘️  Población total REALISTA: {total_population:,.0f} habitantes")
    logger.info(f"📊 Rango de población: {gdf_filtrada['population'].min():.1f} - {gdf_filtrada['population'].max():.1f}")
    
    return gdf_filtrada

@lru_cache(maxsize=1)
def load_population_data():
    """Carga datos de población para renderizado con muchos más puntos para visualización tipo LandScan"""
    # Obtener todos los datos primero
    gdf_all_population = load_all_population_data()
    if gdf_all_population is None:
        return None
    
    try:
        # Usar menos puntos en producción para mejor rendimiento
        if os.environ.get('RAILWAY_ENVIRONMENT'):
            max_points = 25000  # Reducido para Railway
        else:
            max_points = 50000  # Valor para desarrollo local
        
        # Estrategia mixta: combinar puntos de alta y baja población para mejor cobertura
        gdf_high = gdf_all_population.sort_values('population', ascending=False)
        gdf_low = gdf_all_population.sort_values('population', ascending=True)
        
        # Tomar 70% de puntos con mayor población y 30% distribuidos aleatoriamente
        high_count = int(max_points * 0.7)
        remaining_count = max_points - high_count
        
        if len(gdf_all_population) > max_points:
            # Puntos de alta población
            selected_high = gdf_high.head(high_count)
            
            # Puntos adicionales para cobertura espacial (excluir los ya seleccionados)
            remaining_points = gdf_all_population[~gdf_all_population.index.isin(selected_high.index)]
            
            if len(remaining_points) > remaining_count:
                # Seleccionar aleatoriamente para mejor distribución espacial
                selected_low = remaining_points.sample(n=remaining_count, random_state=42)
            else:
                selected_low = remaining_points
            
            # Combinar ambos conjuntos
            gdf_for_map = pd.concat([selected_high, selected_low])
            
            logger.info(f"Estrategia mixta: {len(selected_high)} puntos altos + {len(selected_low)} puntos distribuidos")
        else:
            gdf_for_map = gdf_all_population
            logger.info("Usando todos los puntos disponibles")
        
        logger.info(f"📍 Puntos de población para MAPA: {len(gdf_for_map):,} (tipo LandScan)")
        return gdf_for_map
        
    except Exception as e:
        logger.error(f"Error preparando datos para mapa: {e}")
        return None

@lru_cache(maxsize=1)
def calculate_population_by_canton():
    """Calcula la población total por cantón usando TODOS los puntos (sin límite)"""
    try:
        logger.info("Calculando población por cantón usando TODOS los datos...")
        
        # Cargar datos - USAR TODOS LOS PUNTOS, NO LOS LIMITADOS
        gdf_cantones = load_cantones_data()
        gdf_poblacion = load_all_population_data()  # ¡CAMBIO IMPORTANTE!
        
        if gdf_cantones is None or gdf_poblacion is None:
            logger.warning("No se pudieron cargar los datos necesarios")
            return []
        
        # Asegurar mismo CRS
        if gdf_cantones.crs != gdf_poblacion.crs:
            gdf_cantones = gdf_cantones.to_crs(gdf_poblacion.crs)
        
        # Crear diccionario para almacenar población por cantón
        canton_population = {}
        
        logger.info(f"Procesando {len(gdf_cantones)} cantones con {len(gdf_poblacion)} puntos de población COMPLETOS")
        
        # Optimización: crear un índice espacial para acelerar las consultas
        from shapely.strtree import STRtree
        
        # Crear índice espacial para los puntos de población
        population_geoms = list(gdf_poblacion.geometry)
        population_tree = STRtree(population_geoms)
        
        # Para cada cantón, calcular la suma de población de puntos que intersectan
        for idx, canton in gdf_cantones.iterrows():
            canton_name = canton.get('DPA_DESCAN', f'Canton_{idx}')
            canton_geom = canton.geometry
            
            try:
                # Usar el índice espacial para encontrar candidatos cercanos
                possible_matches_idx = list(population_tree.query(canton_geom))
                
                if possible_matches_idx:
                    # Filtrar solo los que realmente intersectan
                    candidate_points = gdf_poblacion.iloc[possible_matches_idx]
                    points_in_canton = candidate_points[candidate_points.geometry.intersects(canton_geom)]
                    
                    # Sumar la población
                    total_population = points_in_canton['population'].sum() if len(points_in_canton) > 0 else 0
                else:
                    total_population = 0
                
                canton_population[canton_name] = {
                    'name': canton_name,
                    'population': int(total_population),
                    'formatted_population': f"{int(total_population):,}".replace(',', '.'),
                    'points_count': len(candidate_points) if possible_matches_idx else 0  # Para debugging
                }
                
                # Log para los cantones más poblados
                if total_population > 50000:
                    logger.info(f"Cantón {canton_name}: {int(total_population):,} habitantes ({len(candidate_points) if possible_matches_idx else 0} puntos)")
                
            except Exception as e:
                logger.warning(f"Error procesando cantón {canton_name}: {e}")
                canton_population[canton_name] = {
                    'name': canton_name,
                    'population': 0,
                    'formatted_population': '0',
                    'points_count': 0
                }
        
        # Convertir a lista y ordenar por población (mayor a menor)
        population_list = list(canton_population.values())
        population_list.sort(key=lambda x: x['population'], reverse=True)
        
        # Log del resumen
        total_calculated = sum(item['population'] for item in population_list)
        logger.info(f"Población calculada para {len(population_list)} cantones")
        logger.info(f"Población total calculada: {total_calculated:,} habitantes")
        
        # Log top 5 cantones
        top_5_info = [f"{item['name']}: {item['population']:,}" for item in population_list[:5]]
        logger.info(f"Top 5 cantones: {top_5_info}")
        
        return population_list
        
    except Exception as e:
        logger.error(f"Error calculando población por cantón: {e}")
        import traceback
        traceback.print_exc()
        return []

@main_bp.route("/api/population-by-canton")
def get_population_by_canton():
    """API endpoint para obtener datos de población por cantón"""
    try:
        population_data = calculate_population_by_canton()
        return jsonify({
            'success': True,
            'data': population_data
        })
    except Exception as e:
        logger.error(f"Error en API población por cantón: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def add_cantones_to_map(map_obj):
    """Agrega cantones al mapa con información de población en tooltips"""
    gdf_cantones = load_cantones_data()
    if gdf_cantones is None:
        return
        
    # Obtener datos de población por cantón
    population_data = calculate_population_by_canton()
    population_dict = {item['name']: item for item in population_data}
        
    logger.info("Agregando cantones al mapa...")
    
    # Crear geojson con tooltips personalizados
    def style_function(feature):
        return {
            "fillColor": "transparent",
            "color": "black",
            "weight": 1,
            "fillOpacity": 0,
        }
    
    # Agregar cada cantón con tooltip personalizado
    for _, canton in gdf_cantones.iterrows():
        canton_name = canton['DPA_DESCAN']
        population_info = population_dict.get(canton_name, {'formatted_population': 'No disponible'})
        
        folium.GeoJson(
            canton.geometry,
            style_function=style_function,
            tooltip=f"""
            <div style="font-family: Arial, sans-serif; min-width: 150px;">
                <b>Cantón:</b> {canton_name}<br>
                <b>Habitantes:</b> {population_info['formatted_population']}
            </div>
            """
        ).add_to(map_obj)

def add_population_to_map(map_obj):
    """Agrega puntos de población al mapa de forma optimizada"""
    gdf_poblacion = load_population_data()
    if gdf_poblacion is None:
        return
        
    logger.info("Agregando puntos de población al mapa...")
    
    # Crear grupo de capas
    poblacion_group = folium.FeatureGroup(name="Densidad de Población")
    
    # Optimización: crear todos los marcadores en batch
    for _, row in gdf_poblacion.iterrows():
        pop_value = row.get('population', 0)
        region = row.get('region', 'continental')
        color, opacity = get_population_color(pop_value, region)
        
        # Usar tamaño pequeño tipo LandScan para mejor visualización de densidad
        radius = current_app.config.get('GLOBAL_POINT_SIZE', 1.5)  # Reducido para más parecido a LandScan
        
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=radius,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=opacity,
            weight=0.2,  # Bordes más delgados para parecer más al LandScan
        ).add_to(poblacion_group)
    
    poblacion_group.add_to(map_obj)

@main_bp.route("/")
def mapa():
    """Ruta principal optimizada para mejor rendimiento"""
    logger.info("Generando mapa...")
    
    # Crear mapa con configuración optimizada
    m = folium.Map(
        location=[-0.20, -78.50], 
        zoom_start=7,  # Zoom más amplio para ver todo Ecuador
        tiles="cartodbpositron",
        prefer_canvas=True  # Mejor rendimiento para muchos puntos
    )
    
    try:
        # Agregar cantones
        add_cantones_to_map(m)
        
        # Agregar población
        add_population_to_map(m)
        
        logger.info("Mapa generado exitosamente!")
        
    except Exception as e:
        logger.error(f"Error generando mapa: {e}")
        import traceback
        traceback.print_exc()

    return render_template(
        "index.html",
        mapa=m.get_root().render(),
        map_name=m.get_name(),
        ruta_activa="mapa"
    )

@main_bp.route("/api/clear-cache")
def clear_cache():
    """Endpoint para limpiar cache y recalcular datos"""
    try:
        # Limpiar cache de las funciones principales
        load_all_population_data.cache_clear()
        load_population_data.cache_clear()
        calculate_population_by_canton.cache_clear()
        load_cantones_data.cache_clear()
        load_ecuador_boundaries.cache_clear()
        
        logger.info("Cache limpiado exitosamente")
        return jsonify({
            'success': True,
            'message': 'Cache limpiado. Los datos se recalcularán en la próxima consulta.'
        })
    except Exception as e:
        logger.error(f"Error limpiando cache: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def load_geojson_safe(file_path, description="archivo"):
    """Carga un archivo GeoJSON de manera segura con múltiples intentos"""
    try:
        # Convertir a Path para mejor manejo
        path = Path(file_path)
        
        # Verificar que el archivo existe
        if not path.exists():
            logger.error(f"❌ Archivo no encontrado: {path}")
            return None
            
        # Verificar tamaño del archivo
        if path.stat().st_size == 0:
            logger.error(f"❌ Archivo vacío: {path}")
            return None
            
        logger.info(f"📁 Intentando cargar {description}: {path}")
        
        # Método 1: Intentar con geopandas directamente
        try:
            gdf = gpd.read_file(str(path))
            logger.info(f"✅ {description} cargado exitosamente con geopandas")
            return gdf
        except Exception as e1:
            logger.warning(f"⚠️ Fallo método 1 (geopandas): {e1}")
            
        # Método 2: Intentar especificando driver
        try:
            gdf = gpd.read_file(str(path), driver='GeoJSON')
            logger.info(f"✅ {description} cargado exitosamente con driver GeoJSON")
            return gdf
        except Exception as e2:
            logger.warning(f"⚠️ Fallo método 2 (driver GeoJSON): {e2}")
            
        # Método 3: Intentar leyendo como JSON y convirtiendo
        try:
            with open(path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
            logger.info(f"✅ {description} cargado exitosamente como JSON")
            return gdf
        except Exception as e3:
            logger.warning(f"⚠️ Fallo método 3 (JSON): {e3}")
            
        # Método 4: Intentar con diferentes codificaciones
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    geojson_data = json.load(f)
                gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
                logger.info(f"✅ {description} cargado exitosamente con codificación {encoding}")
                return gdf
            except Exception as e4:
                continue
                
        logger.error(f"❌ No se pudo cargar {description} con ningún método")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error inesperado cargando {description}: {e}")
        return None

def generate_map():
    try:
        logger.info("Generando mapa...")
        
        # Definir rutas base
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / "data"
        
        logger.info(f"📁 Directorio base: {base_dir}")
        logger.info(f"📁 Directorio de datos: {data_dir}")
        
        # Listar archivos disponibles
        if data_dir.exists():
            files = list(data_dir.glob("*.geojson"))
            logger.info(f"📋 Archivos GeoJSON encontrados: {[f.name for f in files]}")
        else:
            logger.error(f"❌ Directorio de datos no existe: {data_dir}")
            return None
        
        # Cargar cantones
        cantones_path = data_dir / "cantones.geojson"
        cantones_gdf = load_geojson_safe(cantones_path, "cantones")
        
        if cantones_gdf is None:
            logger.error("❌ No se pudieron cargar los cantones")
            return None
            
        # ...existing code for map generation...
        
    except Exception as e:
        logger.error(f"❌ Error generando mapa: {e}")
        return None

def load_population_data():
    """Carga datos de población con múltiples fallbacks"""
    try:
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / "data"
        
        # Lista de archivos en orden de preferencia
        population_files = [
            "poblacion_ecuador_realistic.geojson",
            "poblacion_ecuador_calibrated.geojson", 
            "poblacion_ecuador_enhanced.geojson",
            "poblacion_ecuador.geojson"
        ]
        
        for filename in population_files:
            file_path = data_dir / filename
            logger.info(f"🎯 Intentando cargar: {filename}")
            
            population_gdf = load_geojson_safe(file_path, f"población ({filename})")
            if population_gdf is not None:
                logger.info(f"✅ Datos de población cargados desde: {filename}")
                return population_gdf
                
        logger.error("❌ No se pudieron cargar datos de población desde ningún archivo")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error cargando datos de población: {e}")
        return None

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/api/cantones')
def get_cantones():
    try:
        cantones_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'cantones.geojson')
        with open(cantones_path, 'r', encoding='utf-8') as f:
            cantones_data = json.load(f)
        return jsonify(cantones_data)
    except FileNotFoundError:
        return jsonify({"error": "Archivo de cantones no encontrado"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Error al procesar datos de cantones"}), 500
    except Exception as e:
        return jsonify({"error": "Error interno del servidor"}), 500

