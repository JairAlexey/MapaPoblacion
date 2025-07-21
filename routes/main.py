from flask import Blueprint, render_template
import folium
import geopandas as gpd
import os
from shapely.geometry import Point
import json

main_bp = Blueprint("main", __name__)

def get_population_color(pop_value, region="continental"):
    """Retorna color basado en la densidad de población, ajustado por región"""
    if region == "galapagos":
        # Escala especial para Galápagos (densidades menores)
        if pop_value < 1:
            return "lightgreen", 0.8
        elif pop_value < 5:
            return "green", 0.8
        elif pop_value < 20:
            return "yellow", 0.9
        elif pop_value < 50:
            return "orange", 0.9
        else:
            return "red", 1.0
    else:
        # Escala estándar para continental
        if pop_value < 50:
            return "green", 0.6
        elif pop_value < 200:
            return "yellow", 0.7
        elif pop_value < 500:
            return "orange", 0.8
        else:
            return "red", 0.9

@main_bp.route("/")
def mapa():
    # Crear el mapa básico centrado en Quito
    m = folium.Map(location=[-0.20, -78.50], zoom_start=11, tiles="cartodbpositron")
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "..", "data")
    
    # Cargar y mostrar cantones
    cantones_path = os.path.join(DATA_DIR, "cantones.geojson")
    try:
        gdf_cantones = gpd.read_file(cantones_path)
        
        # Agregar cantones al mapa
        for _, row in gdf_cantones.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda _: {
                    "fillColor": "transparent",
                    "color": "black",
                    "weight": 2,
                    "fillOpacity": 0,
                },
                tooltip=f"Cantón: {row.get('DPA_DESCAN', 'Sin nombre')}"
            ).add_to(m)
            
    except Exception as e:
        print(f"Error cargando cantones: {e}")
    
    # Cargar y mostrar datos de población
    poblacion_path = os.path.join(DATA_DIR, "poblacion_ecuador_enhanced.geojson")
    ecuador_path = os.path.join(DATA_DIR, "ec.json")
    
    try:
        # Cargar fronteras de Ecuador
        print("Cargando fronteras de Ecuador...")
        gdf_ecuador = gpd.read_file(ecuador_path)
        
        # Crear una geometría unificada de todo Ecuador
        print("Creando geometría unificada...")
        ecuador_union = gdf_ecuador.geometry.unary_union
        
        # Cargar datos de población
        print("Cargando datos de población...")
        gdf_poblacion = gpd.read_file(poblacion_path)
        
        # Asegurar que ambos GeoDataFrames tengan el mismo CRS
        if gdf_poblacion.crs != gdf_ecuador.crs:
            gdf_poblacion = gdf_poblacion.to_crs(gdf_ecuador.crs)
        
        total_puntos = len(gdf_poblacion)
        print(f"Total de puntos de población: {total_puntos}")
        
        # Método más eficiente: usar geopandas para filtrar espacialmente
        print("Filtrando puntos dentro de Ecuador...")
        # Usar both within() e intersects() para incluir islas y territorios separados
        gdf_poblacion_filtrada = gdf_poblacion[
            gdf_poblacion.within(ecuador_union) | 
            gdf_poblacion.intersects(ecuador_union)
        ]
        
        puntos_filtrados = len(gdf_poblacion_filtrada)
        print(f"Puntos filtrados: {puntos_filtrados} de {total_puntos} puntos originales")
        
        # Crear grupo de capas para población
        poblacion_group = folium.FeatureGroup(name="Densidad de Población")
        
        # Agregar solo los puntos que están dentro de Ecuador
        print("Agregando puntos al mapa...")
        for _, row in gdf_poblacion_filtrada.iterrows():
            pop_value = row.get('population', 0)
            region = row.get('region', 'continental')
            color, opacity = get_population_color(pop_value, region)
            
            # Ajustar tamaño basado en región y población
            if region == "galapagos":
                radius = min(6, max(2, pop_value * 0.2))  # Círculos más grandes para islas
            else:
                radius = 3  # Tamaño estándar para continental
            
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=radius,
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=opacity,
                weight=1,
                popup=f"Población: {pop_value:.1f}<br>Región: {region.title()}",
                tooltip=f"Densidad: {pop_value:.1f} hab/km² ({region.title()})"
            ).add_to(poblacion_group)
        
        poblacion_group.add_to(m)
        
        # Agregar control de capas
        folium.LayerControl().add_to(m)
        print("Mapa de población completado!")
            
    except Exception as e:
        print(f"Error cargando datos de población: {e}")
        import traceback
        traceback.print_exc()

    return render_template(
        "index.html",
        mapa=m.get_root().render(),
        map_name=m.get_name(),
        ruta_activa="mapa"
    )

