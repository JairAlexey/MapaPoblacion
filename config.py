# Configuración de la aplicación
import os

class Config:
    # Configuración de Flask
    SECRET_KEY = 'dev-secret-key-change-in-production'
    DEBUG = True
    
    # Configuración del mapa optimizada
    GLOBAL_POINT_SIZE = 2.0
    
    # Configuración de caché
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutos
    
    # Configuración de logging
    LOG_LEVEL = 'INFO'
    
    # Rutas de datos
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    
class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-secret-key-change-this')
    GLOBAL_POINT_SIZE = 1.5  # Puntos más pequeños en producción para mejor rendimiento
    LOG_LEVEL = 'WARNING'  # Menos logging en producción
    
class DevelopmentConfig(Config):
    DEBUG = True
    GLOBAL_POINT_SIZE = 2.0

# Configuración por defecto
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
