import json
import os

class GeoDataProcessor:
    def __init__(self):
        self.data_path = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    def get_cantones_by_provincia(self, provincia_code):
        """Obtiene cantones filtrados por código de provincia"""
        try:
            cantones_path = os.path.join(self.data_path, 'cantones.geojson')
            with open(cantones_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Filtrar cantones por provincia
            filtered_features = [
                feature for feature in data['features']
                if feature['properties']['DPA_PROVIN'] == str(provincia_code).zfill(2)
            ]
            
            return {
                "type": "FeatureCollection",
                "features": filtered_features
            }
        except Exception as e:
            raise Exception(f"Error procesando datos geográficos: {str(e)}")
    
    def get_provincia_names(self):
        """Obtiene lista única de nombres de provincias"""
        try:
            cantones_path = os.path.join(self.data_path, 'cantones.geojson')
            with open(cantones_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            provincias = {}
            for feature in data['features']:
                codigo = feature['properties']['DPA_PROVIN']
                nombre = feature['properties']['DPA_DESPRO']
                provincias[codigo] = nombre
            
            return dict(sorted(provincias.items()))
        except Exception as e:
            raise Exception(f"Error obteniendo provincias: {str(e)}")
