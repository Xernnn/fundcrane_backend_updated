from flask import Flask
from flask_cors import CORS
import os
from flask_mail import Mail

mail = Mail()

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_pyfile('config.py')
    app.config.update(
        MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.googlemail.com',
        MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587),
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME = os.getenv('MAIL_USERNAME'), # Your email address
        MAIL_PASSWORD = os.getenv('MAIL_PASSWORD'), # Your email password or app password
        MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME'),
    )

    mail.init_app(app)
    
    # Import and register blueprints
    from app.routes import payments_bp, documents_bp, user_authentication_bp
    
    app.register_blueprint(payments_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(user_authentication_bp)

    return app