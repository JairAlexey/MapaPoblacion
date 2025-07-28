import os
import gzip
import json
import requests
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def create_minimal_geojson():
    """Crea versiones minimizadas de los archivos GeoJSON para producción"""
    data_dir = Path("data")
    
    # Si ya existen los archivos grandes, crear versiones simplificadas
    large_files = {
        "poblacion_ecuador_realistic.geojson": "poblacion_ecuador_simple.geojson",
        "parroquiasEcuador.geojson": "parroquias_simple.geojson"
    }
    
    for original, simplified in large_files.items():
        original_path = data_dir / original
        simplified_path = data_dir / simplified
        
        if original_path.exists() and not simplified_path.exists():
            try:
                logger.info(f"Simplificando {original}...")
                
                with open(original_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Simplificar geometrías (tomar solo cada 10mo punto para reducir tamaño)
                if 'features' in data:
                    for feature in data['features'][:1000]:  # Limitar a 1000 features
                        if 'geometry' in feature and 'coordinates' in feature['geometry']:
                            coords = feature['geometry']['coordinates']
                            if isinstance(coords, list) and len(coords) > 0:
                                # Simplificar coordenadas
                                if feature['geometry']['type'] == 'Polygon':
                                    for ring in coords:
                                        if len(ring) > 10:
                                            feature['geometry']['coordinates'] = [ring[::5]]  # Cada 5to punto
                
                # Guardar versión simplificada
                with open(simplified_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, separators=(',', ':'))
                
                logger.info(f"✅ Creado {simplified}")
                
            except Exception as e:
                logger.error(f"❌ Error simplificando {original}: {e}")

if __name__ == "__main__":
    create_minimal_geojson()
