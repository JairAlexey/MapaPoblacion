import rasterio
import geojson
import geopandas as gpd
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
import os

def process_landscan_to_geojson(input_tif_path, output_geojson_path, 
                               ecuador_bounds=(-92.0, -5.5, -74.5, 2.5),
                               min_population=1,
                               resample_factor=2):
    """
    Procesa el archivo LandScan TIF y genera un GeoJSON con puntos de población
    
    Args:
        input_tif_path: Ruta al archivo .tif de LandScan
        output_geojson_path: Ruta donde guardar el GeoJSON resultante
        ecuador_bounds: Límites de Ecuador (xmin, ymin, xmax, ymax)
        min_population: Población mínima para incluir un punto
        resample_factor: Factor de remuestreo para reducir resolución (4 = 1/4 de resolución)
    """
    
    print("Procesando archivo LandScan...")
    
    with rasterio.open(input_tif_path) as src:
        print(f"Archivo original: {src.width} x {src.height} píxeles")
        print(f"Bounds originales: {src.bounds}")
        
        # Crear geometría para recortar a Ecuador
        from shapely.geometry import box
        ecuador_geom = box(*ecuador_bounds)
        
        # Recortar el raster a Ecuador
        out_image, out_transform = mask(src, [ecuador_geom], crop=True)
        out_meta = src.meta.copy()
        
        # Actualizar metadatos
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })
        
        # Guardar raster recortado temporalmente
        temp_path = input_tif_path.replace('.tif', '_ecuador_temp.tif')
        with rasterio.open(temp_path, 'w', **out_meta) as temp_dst:
            temp_dst.write(out_image)
        
        # Asegurar que el archivo se cierre completamente
        temp_dst = None
    
    # Reabrir el archivo recortado y remuestrearlo para reducir tamaño
    with rasterio.open(temp_path) as src:
        # Calcular nueva transformación con menor resolución
        new_width = src.width // resample_factor
        new_height = src.height // resample_factor
        
        transform, width, height = calculate_default_transform(
            src.crs, src.crs, new_width, new_height, *src.bounds
        )
        
        # Crear array de salida
        resampled = np.empty((new_height, new_width), dtype=src.dtypes[0])
        
        # Remuestrear
        reproject(
            source=rasterio.band(src, 1),
            destination=resampled,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=src.crs,
            resampling=Resampling.average
        )
        
        print(f"Raster procesado: {new_width} x {new_height} píxeles")
        
        # Convertir a puntos
        features = []
        for row in range(new_height):
            for col in range(new_width):
                pop_value = float(resampled[row, col])
                
                # Filtrar valores significativos
                if pop_value >= min_population and not np.isnan(pop_value):
                    # Obtener coordenadas del centro del píxel
                    lon, lat = rasterio.transform.xy(transform, row, col, offset='center')
                    
                    # Crear feature GeoJSON
                    feature = geojson.Feature(
                        geometry=geojson.Point((lon, lat)),
                        properties={
                            "population": round(pop_value, 2),
                            "pop_class": get_population_class(pop_value)
                        }
                    )
                    features.append(feature)
        
        print(f"Puntos generados: {len(features)}")
        
        # Crear FeatureCollection y guardar
        feature_collection = geojson.FeatureCollection(features)
        
        with open(output_geojson_path, 'w', encoding='utf-8') as f:
            geojson.dump(feature_collection, f, ensure_ascii=False, indent=2)
        
        # Eliminar archivo temporal con manejo de errores
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError as e:
            print(f"Advertencia: No se pudo eliminar archivo temporal: {e}")
        
        print(f"GeoJSON guardado en: {output_geojson_path}")
        return len(features)

def get_population_class(pop_value):
    """Clasifica la población en rangos para styling"""
    if pop_value < 50:
        return "low"
    elif pop_value < 200:
        return "medium"
    elif pop_value < 500:
        return "high"
    else:
        return "very_high"

if __name__ == "__main__":
    # Configuración de rutas
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    
    input_file = os.path.join(DATA_DIR, "landscan-global-2023.tif")
    output_file = os.path.join(DATA_DIR, "poblacion_ecuador.geojson")
    
    if os.path.exists(input_file):
        try:
            num_points = process_landscan_to_geojson(input_file, output_file)
            print(f"✅ Procesamiento completado. {num_points} puntos de población generados.")
        except Exception as e:
            print(f"❌ Error durante el procesamiento: {e}")
    else:
        print(f"❌ No se encontró el archivo: {input_file}")
