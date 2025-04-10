import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    ZOHO_OAUTH_TOKEN = os.getenv('ZOHO_OAUTH_TOKEN')
    MONGO_USERNAME = os.getenv('MONGO_USERNAME')
    MONGO_PASSWORD = os.getenv('MONGO_PASSWORD')
    MONGO_URL = os.getenv('MONGO_URL')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    POSTGRESQL_PARAM = {
        'dbname': os.getenv('POSTGRESQL_DBNAME'),
        'user': 'root',
        'password': os.getenv('POSTGRESQL_PASSWORD'),
        'host': os.getenv('POSTGRESQL_HOST'),
        'port': os.getenv('POSTGRESQL_PORT'),
    }
<<<<<<< HEAD
    SECRET_KEY = os.getenv(('SECRET_KEY')),
    TOS_ACCESS_KEY = os.getenv(('TOS_ACCESS_KEY')),
    TOS_SECRET_KEY = os.getenv(('TOS_SECRET_KEY'))
=======
    SECRET_KEY = os.getenv('SECRET_KEY') or 'a-very-strong-secret-key'
     # Flask-Mail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.googlemail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME') # Your email address
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD') # Your email password or app password
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER') or MAIL_USERNAME

    # Token expiry time (e.g., 1 hour)
    EMAIL_VERIFICATION_TOKEN_MAX_AGE = 3600
>>>>>>> 1c4f4103634e0894c851b500f64e5e699f779d2b
