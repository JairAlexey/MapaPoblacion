import rasterio
import geojson
import geopandas as gpd
import pandas as pd
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
import os
from shapely.geometry import box, Point

def process_realistic_population_map(input_tif_path, cantones_geojson_path, poblacion_excel_path, 
                                   output_geojson_path, ecuador_bounds=(-92.0, -5.5, -74.5, 2.5),
                                   min_population=0.5, resample_factor=1):
    """
    Procesa el archivo LandScan TIF usando datos reales de población por cantones
    para generar un mapa más realista con mejor distribución de puntos.
    
    Args:
        input_tif_path: Ruta al archivo .tif de LandScan
        cantones_geojson_path: Ruta al GeoJSON de cantones
        poblacion_excel_path: Ruta al Excel con población real por cantones
        output_geojson_path: Ruta donde guardar el GeoJSON resultante
        ecuador_bounds: Límites de Ecuador (xmin, ymin, xmax, ymax)
        min_population: Población mínima para incluir un punto
        resample_factor: Factor de remuestreo (1 = resolución completa)
    """
    
    print("� Iniciando procesamiento realista de población...")
    
    # 1. Cargar datos de población real por cantones
    print("📊 Cargando datos de población por cantones...")
    df_poblacion = pd.read_excel(poblacion_excel_path)
    print(f"   ✅ {len(df_poblacion)} cantones cargados")
    
    # 2. Cargar geometrías de cantones
    print("🗺️  Cargando geometrías de cantones...")
    gdf_cantones = gpd.read_file(cantones_geojson_path)
    
    # Convertir códigos para hacer match
    df_poblacion['DPA_CANTON'] = df_poblacion['Código'].astype(str).str.zfill(4)
    gdf_cantones['DPA_CANTON'] = gdf_cantones['DPA_CANTON'].astype(str)
    
    # Unir datos de población con geometrías
    gdf_cantones = gdf_cantones.merge(df_poblacion[['DPA_CANTON', 'Habitantes']], 
                                     on='DPA_CANTON', how='left')
    
    # Llenar valores nulos con 0
    gdf_cantones['Habitantes'] = gdf_cantones['Habitantes'].fillna(0)
    
    print(f"   ✅ {len(gdf_cantones[gdf_cantones['Habitantes'] > 0])} cantones con datos de población")
    
    # 3. Procesar archivo TIF
    print("� Procesando archivo LandScan...")
    
    with rasterio.open(input_tif_path) as src:
        print(f"   📐 Archivo original: {src.width} x {src.height} píxeles")
        
        # Crear geometría para recortar a Ecuador
        ecuador_geom = box(*ecuador_bounds)
        
        # Recortar el raster a Ecuador
        out_image, out_transform = mask(src, [ecuador_geom], crop=True)
        out_meta = src.meta.copy()
        
        # Actualizar metadatos
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "crs": src.crs
        })
        
        # Si hay factor de remuestreo, aplicarlo
        if resample_factor > 1:
            new_width = out_image.shape[2] // resample_factor
            new_height = out_image.shape[1] // resample_factor
            
            transform, _, _ = calculate_default_transform(
                src.crs, src.crs, new_width, new_height, 
                out_transform.xoff, out_transform.yoff + out_transform.f * out_image.shape[1],
                out_transform.xoff + out_transform.a * out_image.shape[2], out_transform.yoff
            )
            
            resampled = np.empty((new_height, new_width), dtype=out_image.dtype)
            reproject(
                source=out_image[0],
                destination=resampled,
                src_transform=out_transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=src.crs,
                resampling=Resampling.average
            )
            
            landscan_data = resampled
            final_transform = transform
            print(f"   📐 Resolución ajustada: {new_width} x {new_height} píxeles")
        else:
            landscan_data = out_image[0]
            final_transform = out_transform
            print(f"   📐 Resolución completa mantenida")
        
        # Limpiar datos NoData y negativos
        nodata_value = src.nodata
        if nodata_value is not None:
            landscan_data[landscan_data == nodata_value] = 0
        landscan_data[landscan_data < 0] = 0
    
    # 4. Generar puntos con distribución realista por cantón
    print("🎯 Generando puntos con distribución realista...")
    
    features = []
    total_points = 0
    total_pop_real = 0
    
    # Reproyectar cantones al mismo CRS del raster si es necesario
    if gdf_cantones.crs != out_meta['crs']:
        gdf_cantones = gdf_cantones.to_crs(out_meta['crs'])
    
    for idx, canton in gdf_cantones.iterrows():
        if canton['Habitantes'] <= 0:
            continue
            
        canton_name = canton.get('DPA_DESCAN', f"Canton_{idx}")
        poblacion_real = canton['Habitantes']
        total_pop_real += poblacion_real
        
        print(f"   🏛️  Procesando {canton_name}: {poblacion_real:,} habitantes")
        
        # Crear máscara del cantón sobre el raster
        try:
            # Obtener bounds del cantón
            bounds = canton['geometry'].bounds
            
            # Calcular índices del raster que intersectan con el cantón
            col_start = max(0, int((bounds[0] - final_transform.xoff) / final_transform.a))
            col_end = min(landscan_data.shape[1], int((bounds[2] - final_transform.xoff) / final_transform.a) + 1)
            row_start = max(0, int((bounds[3] - final_transform.yoff) / final_transform.e))
            row_end = min(landscan_data.shape[0], int((bounds[1] - final_transform.yoff) / final_transform.e) + 1)
            
            # Extraer subset del raster
            subset_data = landscan_data[row_start:row_end, col_start:col_end]
            
            if subset_data.size == 0:
                continue
            
            # Calcular coordenadas para cada píxel en el subset
            points_in_canton = []
            landscan_values = []
            
            for row in range(subset_data.shape[0]):
                for col in range(subset_data.shape[1]):
                    global_row = row_start + row
                    global_col = col_start + col
                    
                    # Coordenadas del píxel
                    lon, lat = rasterio.transform.xy(final_transform, global_row, global_col, offset='center')
                    point = Point(lon, lat)
                    
                    # Verificar si está dentro del cantón
                    if canton['geometry'].contains(point):
                        landscan_val = subset_data[row, col]
                        if landscan_val > 0:
                            points_in_canton.append((lon, lat))
                            landscan_values.append(landscan_val)
            
            if not points_in_canton:
                # Si no hay puntos válidos, crear uno en el centroide
                centroid = canton['geometry'].centroid
                feature = geojson.Feature(
                    geometry=geojson.Point((centroid.x, centroid.y)),
                    properties={
                        "population": poblacion_real,
                        "pop_class": get_population_class(poblacion_real),
                        "canton": canton_name,
                        "source": "centroid"
                    }
                )
                features.append(feature)
                total_points += 1
                continue
            
            # Distribuir población real proporcionalmente
            total_landscan = sum(landscan_values)
            points_generated = 0
            
            for i, (lon, lat) in enumerate(points_in_canton):
                proporcion = landscan_values[i] / total_landscan
                poblacion_pixel = poblacion_real * proporcion
                
                if poblacion_pixel >= min_population:
                    feature = geojson.Feature(
                        geometry=geojson.Point((lon, lat)),
                        properties={
                            "population": round(poblacion_pixel, 2),
                            "pop_class": get_population_class(poblacion_pixel),
                            "canton": canton_name,
                            "source": "distributed",
                            "landscan_value": round(float(landscan_values[i]), 2)
                        }
                    )
                    features.append(feature)
                    points_generated += 1
            
            print(f"      ✅ {points_generated} puntos generados")
            total_points += points_generated
            
        except Exception as e:
            print(f"      ⚠️  Error procesando {canton_name}: {e}")
            # Crear punto en centroide como fallback
            centroid = canton['geometry'].centroid
            feature = geojson.Feature(
                geometry=geojson.Point((centroid.x, centroid.y)),
                properties={
                    "population": poblacion_real,
                    "pop_class": get_population_class(poblacion_real),
                    "canton": canton_name,
                    "source": "fallback"
                }
            )
            features.append(feature)
            total_points += 1
    
    print(f"� Total de puntos generados: {total_points:,}")
    print(f"👥 Población total real: {total_pop_real:,} habitantes")
    
    # 5. Guardar resultado
    print("💾 Guardando GeoJSON...")
    feature_collection = geojson.FeatureCollection(features)
    
    with open(output_geojson_path, 'w', encoding='utf-8') as f:
        geojson.dump(feature_collection, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Archivo guardado en: {output_geojson_path}")
    
    return total_points, total_pop_real

def get_population_class(pop_value):
    """Clasifica la población en rangos para styling"""
    if pop_value < 10:
        return "very_low"
    elif pop_value < 50:
        return "low"
    elif pop_value < 200:
        return "medium"
    elif pop_value < 1000:
        return "high"
    elif pop_value < 5000:
        return "very_high"
    else:
        return "extreme"

if __name__ == "__main__":
    # Configuración de rutas
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    
    input_tif = os.path.join(DATA_DIR, "landscan-global-2023.tif")
    cantones_geojson = os.path.join(DATA_DIR, "cantones.geojson")
    poblacion_excel = os.path.join(DATA_DIR, "PoblacionCantontes.xlsx")
    output_file = os.path.join(DATA_DIR, "poblacion_ecuador_realistic.geojson")
    
    # Verificar archivos
    files_to_check = [
        (input_tif, "LandScan TIF"),
        (cantones_geojson, "Cantones GeoJSON"),
        (poblacion_excel, "Población Excel")
    ]
    
    missing_files = []
    for file_path, description in files_to_check:
        if not os.path.exists(file_path):
            missing_files.append(f"❌ {description}: {file_path}")
        else:
            print(f"✅ {description}: encontrado")
    
    if missing_files:
        print("\nArchivos faltantes:")
        for missing in missing_files:
            print(missing)
    else:
        try:
            print("\n🚀 Iniciando procesamiento...")
            num_points, total_pop = process_realistic_population_map(
                input_tif, cantones_geojson, poblacion_excel, output_file,
                resample_factor=1  # Usar resolución completa para más detalle
            )
            print(f"\n🎉 ¡Procesamiento completado exitosamente!")
            print(f"📈 {num_points:,} puntos de población generados con datos reales")
            print(f"👥 Población total: {total_pop:,} habitantes")
        except Exception as e:
            print(f"\n💥 Error durante el procesamiento: {e}")
            import traceback
            traceback.print_exc()
