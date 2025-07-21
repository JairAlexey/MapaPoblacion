import rasterio
import geojson
import geopandas as gpd
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
import os

def process_landscan_islands_enhanced(input_tif_path, output_geojson_path):
    """
    Procesamiento especializado para islas ecuatorianas con mayor resolución
    """
    
    print("Procesando archivo LandScan con configuración especial para islas...")
    
    # Límites específicos para cada región
    regions = {
        "galapagos": (-92.0, -1.5, -89.0, 1.5),
        "continental": (-81.5, -5.5, -74.5, 2.5)
    }
    
    all_features = []
    
    for region_name, bounds in regions.items():
        print(f"\n--- Procesando región: {region_name.upper()} ---")
        
        with rasterio.open(input_tif_path) as src:
            print(f"Límites de {region_name}: {bounds}")
            
            # Crear geometría para recortar
            from shapely.geometry import box
            region_geom = box(*bounds)
            
            # Recortar el raster a la región específica
            out_image, out_transform = mask(src, [region_geom], crop=True)
            out_meta = src.meta.copy()
            
            # Configuración específica por región
            if region_name == "galapagos":
                # Para Galápagos: mayor resolución y menor umbral
                resample_factor = 1  # Sin reducción de resolución
                min_population = 0.1  # Umbral muy bajo para capturar toda población
                print(f"Configuración Galápagos: factor={resample_factor}, min_pop={min_population}")
            else:
                # Para continental: configuración estándar
                resample_factor = 2
                min_population = 5
                print(f"Configuración Continental: factor={resample_factor}, min_pop={min_population}")
            
            # Actualizar metadatos
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            
            # Guardar raster recortado temporalmente
            temp_path = input_tif_path.replace('.tif', f'_{region_name}_temp.tif')
            with rasterio.open(temp_path, 'w', **out_meta) as temp_dst:
                temp_dst.write(out_image)
            
            temp_dst = None
        
        # Reabrir y procesar
        with rasterio.open(temp_path) as src:
            if resample_factor > 1:
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
                
                array_to_use = resampled
                transform_to_use = transform
                height_to_use = new_height
                width_to_use = new_width
            else:
                # Usar resolución original
                array_to_use = src.read(1)
                transform_to_use = src.transform
                height_to_use = src.height
                width_to_use = src.width
            
            print(f"Procesando {region_name}: {width_to_use} x {height_to_use} píxeles")
            
            # Convertir a puntos
            region_features = []
            for row in range(height_to_use):
                for col in range(width_to_use):
                    pop_value = float(array_to_use[row, col])
                    
                    # Filtrar valores significativos
                    if pop_value >= min_population and not np.isnan(pop_value):
                        # Obtener coordenadas del centro del píxel
                        lon, lat = rasterio.transform.xy(transform_to_use, row, col, offset='center')
                        
                        # Crear feature GeoJSON
                        feature = geojson.Feature(
                            geometry=geojson.Point((lon, lat)),
                            properties={
                                "population": round(pop_value, 2),
                                "pop_class": get_population_class(pop_value),
                                "region": region_name
                            }
                        )
                        region_features.append(feature)
            
            print(f"Puntos generados en {region_name}: {len(region_features)}")
            all_features.extend(region_features)
            
            # Eliminar archivo temporal
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError as e:
                print(f"Advertencia: No se pudo eliminar archivo temporal {temp_path}: {e}")
    
    # Crear FeatureCollection final
    print(f"\nTotal de puntos generados: {len(all_features)}")
    feature_collection = geojson.FeatureCollection(all_features)
    
    with open(output_geojson_path, 'w', encoding='utf-8') as f:
        geojson.dump(feature_collection, f, ensure_ascii=False, indent=2)
    
    print(f"GeoJSON guardado en: {output_geojson_path}")
    return len(all_features)

def get_population_class(pop_value):
    """Clasifica la población en rangos para styling"""
    if pop_value < 10:
        return "very_low"
    elif pop_value < 50:
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
    output_file = os.path.join(DATA_DIR, "poblacion_ecuador_enhanced.geojson")
    
    if os.path.exists(input_file):
        try:
            num_points = process_landscan_islands_enhanced(input_file, output_file)
            print(f"✅ Procesamiento mejorado completado. {num_points} puntos de población generados.")
        except Exception as e:
            print(f"❌ Error durante el procesamiento: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ No se encontró el archivo: {input_file}")
