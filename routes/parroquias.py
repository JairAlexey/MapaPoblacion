from flask import Blueprint, render_template, current_app, jsonify, request
import folium
import geopandas as gpd
import os
from shapely.geometry import Point
import json
from functools import lru_cache
import logging
import pandas as pd

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

parroquias_bp = Blueprint("parroquias", __name__)

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
def load_parroquias_data():
    """Carga datos de parroquias con cache OPTIMIZADO"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "..", "data")
    parroquias_path = os.path.join(DATA_DIR, "parroquiasEcuador.geojson")
    
    try:
        logger.info("🏛️  Cargando datos de parroquias...")
        gdf_parroquias = gpd.read_file(parroquias_path)
        
        logger.info(f"✅ Parroquias cargadas: {len(gdf_parroquias)} parroquias")
        logger.info(f"📋 Columnas disponibles: {list(gdf_parroquias.columns)}")
        
        # Pre-simplificar geometrías para mejor rendimiento
        logger.info("⚡ Pre-simplificando geometrías para mejor rendimiento...")
        gdf_parroquias['geometry'] = gdf_parroquias.geometry.simplify(tolerance=0.001, preserve_topology=True)
        
        logger.info("✅ Geometrías simplificadas exitosamente")
        
        return gdf_parroquias
    except Exception as e:
        logger.error(f"❌ Error cargando parroquias: {e}")
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
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "..", "data")
    
    # USAR DATOS REALISTAS basados en población oficial + LandScan
    poblacion_path = os.path.join(DATA_DIR, "poblacion_ecuador_realistic.geojson")
    
    try:
        logger.info("🎯 Cargando datos REALISTAS de población para parroquias...")
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
        logger.info(f"✅ DATOS REALISTAS cargados para parroquias: {len(gdf_filtrada):,} puntos")
        logger.info(f"🏘️  Población total REALISTA: {total_population:,.0f} habitantes")
        logger.info(f"📊 Rango de población: {gdf_filtrada['population'].min():.1f} - {gdf_filtrada['population'].max():.1f}")
        
        return gdf_filtrada
        
    except Exception as e:
        logger.error(f"❌ Error cargando datos realistas: {e}")
        return None

@lru_cache(maxsize=1)
def load_population_data():
    """Carga datos de población IGUAL que el mapa de cantones - MISMA VISUALIZACIÓN"""
    # Obtener todos los datos primero
    gdf_all_population = load_all_population_data()
    if gdf_all_population is None:
        return None
    
    try:
        # USAR LA MISMA CONFIGURACIÓN QUE EL MAPA DE CANTONES
        if os.environ.get('RAILWAY_ENVIRONMENT'):
            max_points = 25000  # Igual que cantones
        else:
            max_points = 50000  # Igual que cantones
        
        # MISMA ESTRATEGIA que el mapa de cantones
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
        
        logger.info(f"📍 Puntos de población para MAPA de parroquias: {len(gdf_for_map):,} (IGUAL que cantones)")
        return gdf_for_map
        
    except Exception as e:
        logger.error(f"Error preparando datos para mapa: {e}")
        return None

@lru_cache(maxsize=1)
def calculate_population_by_parroquia():
    """Calcula la población total por parroquia usando TODOS los puntos (igual que cantones)"""
    try:
        logger.info("Calculando población por parroquia usando TODOS los datos...")
        
        # Cargar datos - USAR TODOS LOS PUNTOS, NO LOS LIMITADOS
        gdf_parroquias = load_parroquias_data()
        gdf_poblacion = load_all_population_data()  # TODOS los puntos como en cantones
        
        if gdf_parroquias is None or gdf_poblacion is None:
            logger.warning("No se pudieron cargar los datos necesarios")
            return []
        
        # Asegurar mismo CRS
        if gdf_parroquias.crs != gdf_poblacion.crs:
            gdf_parroquias = gdf_parroquias.to_crs(gdf_poblacion.crs)
        
        # Crear diccionario para almacenar población por parroquia
        parroquia_population = {}
        
        logger.info(f"Procesando {len(gdf_parroquias)} parroquias con {len(gdf_poblacion)} puntos de población COMPLETOS")
        
        # Optimización: crear un índice espacial para acelerar las consultas
        from shapely.strtree import STRtree
        
        # Crear índice espacial para los puntos de población
        population_geoms = list(gdf_poblacion.geometry)
        population_tree = STRtree(population_geoms)
        
        # Para cada parroquia, calcular la suma de población de puntos que intersectan
        for idx, parroquia in gdf_parroquias.iterrows():
            parroquia_name = parroquia.get('PARROQUIA', f'Parroquia_{idx}')
            parroquia_geom = parroquia.geometry
            
            try:
                # Usar el índice espacial para encontrar candidatos cercanos
                possible_matches_idx = list(population_tree.query(parroquia_geom))
                
                if possible_matches_idx:
                    # Filtrar solo los que realmente intersectan
                    candidate_points = gdf_poblacion.iloc[possible_matches_idx]
                    points_in_parroquia = candidate_points[candidate_points.geometry.intersects(parroquia_geom)]
                    
                    # Sumar la población
                    total_population = points_in_parroquia['population'].sum() if len(points_in_parroquia) > 0 else 0
                else:
                    total_population = 0
                
                # Agregar información adicional como provincia y cantón
                provincia = parroquia.get('PROVINCIA', 'N/A')
                canton = parroquia.get('CANTON', 'N/A')
                
                parroquia_population[parroquia_name] = {
                    'name': parroquia_name,
                    'provincia': provincia,
                    'canton': canton,
                    'population': int(total_population),
                    'formatted_population': f"{int(total_population):,}".replace(',', '.'),
                    'points_count': len(candidate_points) if possible_matches_idx else 0  # Para debugging
                }
                
                # Log para las parroquias más pobladas
                if total_population > 10000:
                    logger.info(f"Parroquia {parroquia_name} ({provincia}): {int(total_population):,} habitantes ({len(candidate_points) if possible_matches_idx else 0} puntos)")
                
            except Exception as e:
                logger.warning(f"Error procesando parroquia {parroquia_name}: {e}")
                parroquia_population[parroquia_name] = {
                    'name': parroquia_name,
                    'provincia': parroquia.get('PROVINCIA', 'N/A'),
                    'canton': parroquia.get('CANTON', 'N/A'),
                    'population': 0,
                    'formatted_population': '0',
                    'points_count': 0
                }
        
        # Convertir a lista y ordenar por población (mayor a menor)
        population_list = list(parroquia_population.values())
        population_list.sort(key=lambda x: x['population'], reverse=True)
        
        # Log del resumen
        total_calculated = sum(item['population'] for item in population_list)
        logger.info(f"Población calculada para {len(population_list)} parroquias")
        logger.info(f"Población total calculada: {total_calculated:,} habitantes")
        
        # Log top 5 parroquias
        top_5_info = [f"{item['name']} ({item['provincia']}): {item['population']:,}" for item in population_list[:5]]
        logger.info(f"Top 5 parroquias: {top_5_info}")
        
        return population_list
        
    except Exception as e:
        logger.error(f"Error calculando población por parroquia: {e}")
        import traceback
        traceback.print_exc()
        return []

@parroquias_bp.route("/api/population-by-parroquia")
def get_population_by_parroquia():
    """API endpoint para obtener datos de población por parroquia"""
    try:
        population_data = calculate_population_by_parroquia()
        return jsonify({
            'success': True,
            'data': population_data
        })
    except Exception as e:
        logger.error(f"Error en API población por parroquia: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def add_parroquias_to_map(map_obj):
    """Agrega parroquias al mapa con información de población en tooltips (igual que cantones)"""
    gdf_parroquias = load_parroquias_data()
    if gdf_parroquias is None:
        return
        
    # Obtener datos de población por parroquia
    population_data = calculate_population_by_parroquia()
    population_dict = {item['name']: item for item in population_data}
        
    logger.info("Agregando parroquias al mapa...")
    
    # Crear geojson con tooltips personalizados (IGUAL que cantones)
    def style_function(feature):
        return {
            "fillColor": "transparent",
            "color": "black",  # Color negro como en cantones
            "weight": 1,
            "fillOpacity": 0,
        }
    
    # Agregar cada parroquia con tooltip personalizado
    for _, parroquia in gdf_parroquias.iterrows():
        parroquia_name = parroquia['PARROQUIA']
        population_info = population_dict.get(parroquia_name, {'formatted_population': 'No disponible'})
        
        folium.GeoJson(
            parroquia.geometry,
            style_function=style_function,
            tooltip=f"""
            <div style="font-family: Arial, sans-serif; min-width: 150px;">
                <b>Parroquia:</b> {parroquia_name}<br>
                <b>Habitantes:</b> {population_info['formatted_population']}
            </div>
            """
        ).add_to(map_obj)

def add_population_to_map(map_obj):
    """Agrega puntos de población al mapa EXACTAMENTE igual que cantones"""
    gdf_poblacion = load_population_data()
    if gdf_poblacion is None:
        return
        
    logger.info("Agregando puntos de población al mapa...")
    
    # Crear grupo de capas
    poblacion_group = folium.FeatureGroup(name="Densidad de Población")
    
    # EXACTAMENTE IGUAL que en cantones
    for _, row in gdf_poblacion.iterrows():
        pop_value = row.get('population', 0)
        region = row.get('region', 'continental')
        color, opacity = get_population_color(pop_value, region)
        
        # Usar tamaño pequeño tipo LandScan para mejor visualización de densidad
        radius = current_app.config.get('GLOBAL_POINT_SIZE', 1.5)  # IGUAL que cantones
        
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=radius,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=opacity,
            weight=0.2,  # IGUAL que cantones
        ).add_to(poblacion_group)
    
    poblacion_group.add_to(map_obj)

@parroquias_bp.route("/parroquias")
def mapa_parroquias():
    """Ruta principal para el mapa de parroquias OPTIMIZADO"""
    logger.info("🚀 Generando mapa de parroquias optimizado...")
    
    # Crear mapa con configuración súper optimizada
    m = folium.Map(
        location=[-0.20, -78.50], 
        zoom_start=6,  # Zoom un poco menor para ver mejor las parroquias
        tiles="cartodbpositron",
        prefer_canvas=True,  # Mejor rendimiento para muchos puntos
        max_zoom=18,
        control_scale=True
    )
    
    try:
        logger.info("📍 Agregando puntos de población...")
        # Agregar población PRIMERO (más rápido)
        add_population_to_map(m)
        
        logger.info("🗺️  Agregando límites de parroquias...")
        # Agregar parroquias DESPUÉS
        add_parroquias_to_map(m)
        
        logger.info("✅ Mapa de parroquias generado exitosamente!")
        
    except Exception as e:
        logger.error(f"❌ Error generando mapa de parroquias: {e}")
        import traceback
        traceback.print_exc()
        
        # En caso de error, crear un mapa básico
        logger.info("🔄 Creando mapa de fallback...")
        m = folium.Map(
            location=[-0.20, -78.50], 
            zoom_start=6,
            tiles="OpenStreetMap"
        )
        
        # Agregar solo mensaje de error
        folium.Marker(
            [-0.20, -78.50],
            popup="Error cargando datos de parroquias. Intenta recargar la página.",
            icon=folium.Icon(color='red', icon='exclamation-triangle')
        ).add_to(m)

    return render_template(
        "parroquias.html",
        mapa=m.get_root().render(),
        map_name=m.get_name(),
        ruta_activa="parroquias"
    )

@parroquias_bp.route("/api/clear-cache-parroquias")
def clear_cache_parroquias():
    """Endpoint para limpiar cache y recalcular datos de parroquias"""
    try:
        # Limpiar cache de las funciones principales
        load_all_population_data.cache_clear()
        load_population_data.cache_clear()
        calculate_population_by_parroquia.cache_clear()
        load_parroquias_data.cache_clear()
        load_ecuador_boundaries.cache_clear()
        
        logger.info("Cache de parroquias limpiado exitosamente")
        return jsonify({
            'success': True,
            'message': 'Cache de parroquias limpiado. Los datos se recalcularán en la próxima consulta.'
        })
    except Exception as e:
        logger.error(f"Error limpiando cache de parroquias: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@parroquias_bp.route("/api/test-parroquias-data")
def test_parroquias_data():
    """Endpoint de prueba para verificar que los datos son correctos"""
    try:
        population_data = calculate_population_by_parroquia()
        
        # Tomar los primeros 10 elementos para verificar
        test_data = population_data[:10] if population_data else []
        
        # Verificar estructura
        sample_record = test_data[0] if test_data else None
        
        return jsonify({
            'success': True,
            'total_records': len(population_data),
            'sample_records': test_data,
            'sample_structure': list(sample_record.keys()) if sample_record else [],
            'verification': {
                'has_canton_field': 'canton' in (sample_record or {}),
                'has_provincia_field': 'provincia' in (sample_record or {}),
                'has_name_field': 'name' in (sample_record or {}),
                'first_record_name': sample_record.get('name') if sample_record else None,
                'first_record_canton': sample_record.get('canton') if sample_record else None,
                'first_record_provincia': sample_record.get('provincia') if sample_record else None
            }
        })
    except Exception as e:
        logger.error(f"Error en test de parroquias: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@parroquias_bp.route('/api/parroquias/<provincia_id>')
def get_parroquias_by_provincia(provincia_id):
    # Validar que provincia_id sea numérico
    try:
        provincia_id = int(provincia_id)
        if provincia_id < 1 or provincia_id > 24:  # Ecuador tiene 24 provincias
            return jsonify({"error": "ID de provincia inválido"}), 400
    except ValueError:
        return jsonify({"error": "ID de provincia debe ser numérico"}), 400
    
    # ...existing code for data processing...
    
    return jsonify({"parroquias": []})  # Placeholder
