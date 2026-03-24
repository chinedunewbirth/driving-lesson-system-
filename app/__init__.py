from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
import redis
import logging
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
csrf = CSRFProtect()
mail = Mail()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

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

    # Initialize Prometheus metrics
    from app.metrics import init_metrics
    init_metrics(app)

    # Initialize OAuth social login
    from app.oauth import init_oauth
    init_oauth(app)

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

    # CLI command to send automated lesson reminders
    @app.cli.command('send-reminders')
    def send_reminders():
        """Send automated reminders for upcoming lessons (24h and 1h before)."""
        from app.models import Lesson, User
        from app.notifications import notify_user
        from datetime import datetime, timedelta

        now = datetime.now()
        window_24h = now + timedelta(hours=24)
        window_1h = now + timedelta(hours=1)

        sent_count = 0

        # 24-hour reminders: lessons between now+23h and now+25h
        lessons_24h = Lesson.query.filter(
            Lesson.status == 'confirmed',
            Lesson.reminder_24h_sent.is_(False),
            Lesson.date.isnot(None),
            Lesson.time.isnot(None),
        ).all()

        for lesson in lessons_24h:
            lesson_dt = datetime.combine(lesson.date, lesson.time)
            if now + timedelta(hours=23) <= lesson_dt <= now + timedelta(hours=25):
                student = User.query.get(lesson.student_id)
                instructor = User.query.get(lesson.instructor_id)
                if student and instructor:
                    notify_user(student, 'lesson_reminder', **{
                        'recipient_name': student.username,
                        'instructor_name': instructor.username,
                        'date': lesson.date.strftime('%b %d, %Y'),
                        'time': lesson.time.strftime('%I:%M %p'),
                        'duration': round((lesson.duration or 60) / 60, 1),
                        'pickup_address': lesson.pickup_address or '',
                    })
                    lesson.reminder_24h_sent = True
                    sent_count += 1

        # 1-hour reminders: lessons between now+30m and now+1h30m
        lessons_1h = Lesson.query.filter(
            Lesson.status == 'confirmed',
            Lesson.reminder_1h_sent.is_(False),
            Lesson.date.isnot(None),
            Lesson.time.isnot(None),
        ).all()

        for lesson in lessons_1h:
            lesson_dt = datetime.combine(lesson.date, lesson.time)
            if now + timedelta(minutes=30) <= lesson_dt <= now + timedelta(minutes=90):
                student = User.query.get(lesson.student_id)
                instructor = User.query.get(lesson.instructor_id)
                if student and instructor:
                    notify_user(student, 'lesson_reminder', **{
                        'recipient_name': student.username,
                        'instructor_name': instructor.username,
                        'date': lesson.date.strftime('%b %d, %Y'),
                        'time': lesson.time.strftime('%I:%M %p'),
                        'duration': round((lesson.duration or 60) / 60, 1),
                        'pickup_address': lesson.pickup_address or '',
                    })
                    lesson.reminder_1h_sent = True
                    sent_count += 1

        db.session.commit()
        print(f'Sent {sent_count} lesson reminder(s).')

    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'ai_enabled': app.config.get('USE_AI_CHATBOT', False)}

    return app
