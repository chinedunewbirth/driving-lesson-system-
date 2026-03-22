from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import redis
import logging
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    csrf.init_app(app)

    # Initialize Redis for conversation storage
    if app.config.get('REDIS_URL'):
        try:
            app.redis = redis.from_url(app.config['REDIS_URL'])
        except Exception as e:
            app.logger.warning(f"Could not connect to Redis: {e}")
            app.redis = None
    else:
        app.redis = None

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO')),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Register blueprints
    from app.routes import auth, main, student, instructor, admin, chatbot
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(instructor.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(chatbot.bp)

    # CLI command to create admin user
    @app.cli.command('create-admin')
    def create_admin():
        """Create the default admin user."""
        from app.models import User
        if User.query.filter_by(role='admin').first():
            print('Admin user already exists.')
            return
        admin_user = User(username='admin', email='admin@drivesmart.com', role='admin')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print('Admin user created: admin@drivesmart.com / admin123')

    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'ai_enabled': app.config.get('USE_AI_CHATBOT', False)}

    return app