# Configuración de la aplicación
import os
import logging

class Config:
    # Configuración de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
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
    LOG_LEVEL = logging.WARNING
    
    # Configuración de logging para producción
    @staticmethod
    def init_app(app):
        # Log de errores a stderr
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.WARNING)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        file_handler.setFormatter(formatter)
        app.logger.addHandler(file_handler)

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    GLOBAL_POINT_SIZE = 2.0

# Configuración por defecto
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
