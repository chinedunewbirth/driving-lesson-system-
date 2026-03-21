import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    USE_AI_CHATBOT = os.environ.get('USE_AI_CHATBOT', 'true').lower() == 'true'
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    # Redis Configuration for conversation storage
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Security
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'false').lower() == 'true'

    # Rate limiting
    CHAT_RATE_LIMIT = int(os.environ.get('CHAT_RATE_LIMIT', '60'))  # messages per hour

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # Stripe Payment Configuration
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    LESSON_PRICE_GBP = float(os.environ.get('LESSON_PRICE_GBP', '35.00'))

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    USE_AI_CHATBOT = False  # Disable AI in tests
    WTF_CSRF_ENABLED = False