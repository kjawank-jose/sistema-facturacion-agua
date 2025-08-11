import os

class Config:
    # Configuración básica
    DEBUG = os.getenv('DEBUG', 'False') == 'True'
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')

    # Configuración de la base de datos
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '5432'))
    DB_NAME = os.getenv('DB_NAME', 'facturacion_agua')
    DB_USER = os.getenv('DB_USER', 'usuario')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'contraseña')

    # Otros parámetros de configuración
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    API_URL = os.getenv('API_URL', 'http://localhost:8000')

    @classmethod
    def database_uri(cls):
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"