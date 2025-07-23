# 🗺️ Mapa de Población de Ecuador

Este proyecto es una aplicación web desarrollada en Flask que visualiza la densidad poblacional de Ecuador mediante mapas interactivos. La aplicación muestra la distribución de habitantes por cantones y parroquias utilizando datos realistas de población y tecnología de mapas de calor.

## 📊 ¿Cómo se calculan los habitantes?

El sistema utiliza una metodología híbrida que combina:

1. **Datos LandScan Global 2023**: Dataset mundial de distribución poblacional de alta resolución
2. **Datos del Censo Ecuador**: Información oficial de población por cantones
3. **Procesamiento Realista**: Algoritmo que redistribuye la población usando:
   - Archivos GeoJSON de límites cantonales y parroquiales
   - Datos de población real por cantones (Excel)
   - Filtros espaciales para Ecuador continental e insular

### Escalas de Densidad Poblacional
- 🔵 **Muy baja**: < 5 hab/km²
- 🟢 **Baja**: 5-25 hab/km²
- 🟡 **Moderada**: 25-500 hab/km²
- 🟠 **Alta**: 500-1500 hab/km²
- 🔴 **Muy alta**: 1500-5000 hab/km²
- 🔴 **Extrema**: > 5000 hab/km²

## 🚀 Instalación y Ejecución

### Prerrequisitos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### 1. Crear entorno virtual
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Ejecutar la aplicación
```bash
python app.py
```

La aplicación estará disponible en: `http://localhost:5001`

## 📁 Estructura del Proyecto

- `app.py` - Aplicación principal Flask
- `config.py` - Configuraciones del proyecto
- `routes/` - Rutas y lógica de la aplicación
- `templates/` - Plantillas HTML
- `static/` - Archivos CSS y recursos estáticos
- `data/` - Datasets de población y límites geográficos
- `utils/` - Utilidades para procesamiento de datos

## 🌐 Despliegue

El proyecto está configurado para desplegarse en Railway con los archivos:
- `Procfile` - Comando de inicio para producción
- `runtime.txt` - Versión de Python
- `requirements.txt` - Dependencias del proyecto
