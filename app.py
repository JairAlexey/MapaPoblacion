from flask import Flask
from routes.main import main_bp
from routes.parroquias import parroquias_bp
from config import config
import os

app = Flask(__name__)

# Configurar la aplicación para producción en Railway
if os.environ.get('RAILWAY_ENVIRONMENT'):
    app.config.from_object(config['production'])
else:
    app.config.from_object(config['development'])

app.register_blueprint(main_bp)
app.register_blueprint(parroquias_bp)

# Configurar headers de seguridad
@app.after_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)
