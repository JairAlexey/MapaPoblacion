import geopandas as gpd
import pandas as pd
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_geojson_with_fallback(base_filename, description="archivo"):
    """Carga archivos GeoJSON con múltiples fallbacks para diferentes entornos"""
    
    data_dir = get_data_directory()
    if not data_dir:
        return None
    
    # Lista de archivos candidatos en orden de preferencia
    candidates = [
        base_filename,  # Archivo original
        base_filename.replace('.geojson', '_simple.geojson'),  # Versión simplificada
        base_filename.replace('.geojson', '_minimal.geojson'),  # Versión mínima
        'cantones.geojson' if 'poblacion' in base_filename else base_filename  # Fallback a cantones
    ]
    
    for candidate in candidates:
        file_path = data_dir / candidate
        
        if not file_path.exists():
            continue
            
        try:
            logger.info(f"📁 Intentando cargar {description}: {candidate}")
            
            # Verificar tamaño del archivo
            file_size = file_path.stat().st_size
            if file_size == 0:
                logger.warning(f"⚠️ Archivo vacío: {candidate}")
                continue
            
            logger.info(f"📊 Tamaño del archivo: {file_size:,} bytes")
            
            # Intentar múltiples métodos de carga
            gdf = None
            
            # Método 1: GeoPandas directo
            try:
                gdf = gpd.read_file(str(file_path))
                logger.info(f"✅ Cargado con geopandas: {len(gdf)} features")
            except Exception as e1:
                logger.warning(f"⚠️ Fallo método geopandas: {e1}")
                
                # Método 2: JSON manual
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if 'features' in data:
                        gdf = gpd.GeoDataFrame.from_features(data['features'])
                        logger.info(f"✅ Cargado como JSON: {len(gdf)} features")
                    else:
                        raise ValueError("No se encontraron features en el GeoJSON")
                        
                except Exception as e2:
                    logger.warning(f"⚠️ Fallo método JSON: {e2}")
                    continue
            
            if gdf is not None and len(gdf) > 0:
                # Asegurar CRS correcto
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                
                logger.info(f"✅ {description} cargado exitosamente desde {candidate}")
                return gdf
                
        except Exception as e:
            logger.warning(f"⚠️ Error cargando {candidate}: {e}")
            continue
    
    logger.error(f"❌ No se pudo cargar {description} desde ningún archivo")
    return None

def get_data_directory():
    """Obtiene el directorio de datos correcto para el entorno"""
    possible_dirs = [
        Path(__file__).parent.parent / "data",  # Desarrollo local
        Path("/app/data"),  # Railway
        Path("./data"),  # Relativo
        Path("../data")  # Un nivel arriba
    ]
    
    for data_dir in possible_dirs:
        if data_dir.exists():
            logger.info(f"📁 Directorio de datos: {data_dir}")
            
            # Listar archivos disponibles
            geojson_files = list(data_dir.glob("*.geojson"))
            logger.info(f"📋 Archivos disponibles: {[f.name for f in geojson_files]}")
            
            return data_dir
    
    logger.error("❌ No se encontró directorio de datos")
    return None

# Funciones específicas para cada tipo de datos
def load_cantones():
    """Carga datos de cantones"""
    return load_geojson_with_fallback("cantones.geojson", "cantones")

def load_population_data():
    """Carga datos de población con fallbacks"""
    return load_geojson_with_fallback("poblacion_ecuador_realistic.geojson", "población")

def load_parroquias():
    """Carga datos de parroquias con fallbacks"""
    return load_geojson_with_fallback("parroquiasEcuador.geojson", "parroquias")
