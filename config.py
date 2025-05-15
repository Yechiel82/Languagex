import os

class Config:
    SECRET_KEY = "7373"
    SQLALCHEMY_DATABASE_URI = 'postgresql://yechiel@localhost/languagex'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API configuration
    CLOUD_API_URL = os.getenv('CLOUD_API_URL', 'https://51ce-103-119-147-234.ngrok-free.app')
    CLOUD_API_GRAMMAR_URL = os.getenv('CLOUD_API_Grammar_URL', 'https://51ce-103-119-147-234.ngrok-free.app')
    
    # File upload configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload size