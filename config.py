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

    # Email Configuration (Flask-Mail)
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'false').lower() == 'true'
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get(
        'MAIL_DEFAULT_SENDER', 'noreply@drivesmart.com'
    )

    # WhatsApp Configuration (Twilio)
    WHATSAPP_ENABLED = os.environ.get(
        'WHATSAPP_ENABLED', 'True'
    ).lower() == 'true'
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_WHATSAPP_FROM = os.environ.get(
        'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886'
    )

    # SMS Configuration (Twilio)
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'false').lower() == 'true'
    TWILIO_SMS_FROM = os.environ.get('TWILIO_SMS_FROM', '')

    # OAuth / Social Login
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', '')
    GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID', '')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET', '')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    USE_AI_CHATBOT = True  # Disable AI in tests
    WTF_CSRF_ENABLED = True
    MAIL_ENABLED = True
    WHATSAPP_ENABLED = True
