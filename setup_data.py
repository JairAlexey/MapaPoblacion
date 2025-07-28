import os
import requests
import json
from pathlib import Path
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_data_directory():
    """Configura el directorio de datos"""
    # En Railway, usar /app/data
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        data_dir = Path("/app/data")
    else:
        # En desarrollo local
        data_dir = Path(__file__).parent / "data"
    
    data_dir.mkdir(exist_ok=True)
    logger.info(f"📁 Directorio de datos: {data_dir}")
    return data_dir

def download_from_github(filename, github_url, data_dir):
    """Descarga archivos desde GitHub"""
    file_path = data_dir / filename
    
    if file_path.exists() and file_path.stat().st_size > 0:
        logger.info(f"✅ {filename} ya existe")
        return True
    
    try:
        logger.info(f"⬇️ Descargando {filename}...")
        
        headers = {
            'User-Agent': 'Railway-App/1.0',
            'Accept': 'application/octet-stream'
        }
        
        response = requests.get(github_url, headers=headers, timeout=300, stream=True)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = file_path.stat().st_size
        logger.info(f"✅ {filename} descargado ({file_size:,} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error descargando {filename}: {e}")
        if file_path.exists():
            file_path.unlink()
        return False

def create_minimal_fallback_data(data_dir):
    """Crea datos mínimos de fallback"""
    logger.info("🔧 Creando datos de fallback...")
    
    cantones_fallback = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "DPA_CANTON": "QUITO",
                    "DPA_DESPRO": "PICHINCHA",
                    "DPA_PROVIN": "17"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-78.6, -0.4], [-78.4, -0.4], 
                        [-78.4, -0.1], [-78.6, -0.1], [-78.6, -0.4]
                    ]]
                }
            }
        ]
    }
    
    poblacion_fallback = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"population": 100},
                "geometry": {"type": "Point", "coordinates": [-78.5, -0.25]}
            }
        ]
    }
    
    files_to_create = {
        "cantones.geojson": cantones_fallback,
        "poblacion_ecuador_realistic.geojson": poblacion_fallback
    }
    
    for filename, data in files_to_create.items():
        file_path = data_dir / filename
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            logger.info(f"✅ Creado {filename} de fallback")

def main():
    """Función principal"""
    logger.info("🚀 Iniciando configuración de datos...")
    
    data_dir = setup_data_directory()
    
    # REEMPLAZA ESTAS URLs CON LAS DE TU RELEASE
    files_to_download = {
        "cantones.geojson": "https://github.com/JairAlexey/MapaPoblacion/releases/download/v1.0/cantones.geojson",
        "poblacion_ecuador_realistic.geojson": "https://github.com/JairAlexey/MapaPoblacion/releases/download/v1.0/poblacion_ecuador_realistic.geojson",
        "parroquiasEcuador.geojson": "https://github.com/JairAlexey/MapaPoblacion/releases/download/v1.0/parroquiasEcuador.geojson"
    }
    
    success_count = 0
    for filename, url in files_to_download.items():
        if download_from_github(filename, url, data_dir):
            success_count += 1
        time.sleep(2)
    
    if success_count == 0:
        logger.warning("⚠️ Usando datos de fallback")
        create_minimal_fallback_data(data_dir)
    
    geojson_files = list(data_dir.glob("*.geojson"))
    logger.info(f"📊 Archivos disponibles: {[f.name for f in geojson_files]}")
    
    logger.info("✅ Configuración completada")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
def main():
    """Función principal para configurar datos"""
    logger.info("🚀 Iniciando configuración de datos...")
    
    # Configurar directorio
    data_dir = setup_data_directory()
    
    # URLs de tus archivos (tendrás que reemplazar con tus URLs reales)
    files_to_download = {
        "cantones.geojson": "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/data/cantones.geojson",
        # Para archivos grandes, mejor usar GitHub Releases:
        # "poblacion_ecuador_realistic.geojson": "https://github.com/TU_USUARIO/TU_REPO/releases/download/v1.0/poblacion_ecuador_realistic.geojson"
    }
    
    # Intentar descargar archivos
    success_count = 0
    for filename, url in files_to_download.items():
        if download_from_github(filename, url, data_dir):
            success_count += 1
        time.sleep(1)  # Pausa entre descargas
    
    # Si no se pudieron descargar archivos, crear fallbacks
    if success_count == 0:
        logger.warning("⚠️ No se pudieron descargar archivos, usando datos de fallback")
        create_minimal_fallback_data(data_dir)
    
    # Verificar archivos finales
    geojson_files = list(data_dir.glob("*.geojson"))
    logger.info(f"📊 Archivos disponibles: {[f.name for f in geojson_files]}")
    
    if len(geojson_files) > 0:
        logger.info("✅ Configuración de datos completada exitosamente")
        return True
    else:
        logger.error("❌ No se pudieron configurar los datos")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
