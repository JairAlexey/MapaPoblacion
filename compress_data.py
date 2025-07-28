import gzip
import json
from pathlib import Path

def compress_geojson_files():
    """Comprime archivos GeoJSON grandes para deployment"""
    data_dir = Path("data")
    
    for geojson_file in data_dir.glob("*.geojson"):
        # Leer archivo original
        with open(geojson_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Comprimir y guardar
        compressed_file = geojson_file.with_suffix('.geojson.gz')
        with gzip.open(compressed_file, 'wt', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))
        
        print(f"✅ Comprimido: {geojson_file.name} -> {compressed_file.name}")
        
        # Verificar tamaño
        original_size = geojson_file.stat().st_size
        compressed_size = compressed_file.stat().st_size
        reduction = (1 - compressed_size/original_size) * 100
        print(f"   Reducción: {reduction:.1f}% ({original_size:,} -> {compressed_size:,} bytes)")

if __name__ == "__main__":
    compress_geojson_files()
