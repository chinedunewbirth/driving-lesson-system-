from app import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer
from flask import current_app


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='student')  # admin, instructor, student
    email_confirmed = db.Column(db.Boolean, default=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    def generate_confirmation_token(self):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.email, salt='email-confirm')

    @staticmethod
    def verify_confirmation_token(token, max_age=86400):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='email-confirm', max_age=max_age)
        except Exception:
            return None
        return User.query.filter_by(email=email).first()

    def generate_reset_token(self):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.email, salt='password-reset')

    @staticmethod
    def verify_reset_token(token, max_age=3600):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='password-reset', max_age=max_age)
        except Exception:
            return None
        return User.query.filter_by(email=email).first()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def is_instructor(self):
        return self.role == 'instructor'

    def is_student(self):
        return self.role == 'student'


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class InstructorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    bio = db.Column(db.String(500))
    hourly_rate = db.Column(db.Float)
    address = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    service_radius_km = db.Column(db.Float, default=15.0)
    phone = db.Column(db.String(20))
    stripe_connect_account_id = db.Column(db.String(255), nullable=True)
    user = db.relationship('User', backref=db.backref('instructor_profile', uselist=False))


class InstructorAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    day_of_week = db.Column(db.Integer)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    instructor = db.relationship('User', backref='availability_slots')


class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    test_passed = db.Column(db.Boolean, default=False)
    test_passed_date = db.Column(db.Date, nullable=True)
    user = db.relationship('User', backref=db.backref('student_profile', uselist=False))


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    duration = db.Column(db.Integer)  # minutes
    status = db.Column(db.String(20), default='confirmed')  # confirmed, cancelled, completed
    pickup_address = db.Column(db.String(255))
    pickup_lat = db.Column(db.Float)
    pickup_lng = db.Column(db.Float)
    reminder_24h_sent = db.Column(db.Boolean, default=False)
    reminder_1h_sent = db.Column(db.Boolean, default=False)

    student = db.relationship('User', foreign_keys=[student_id], backref='student_lessons')
    instructor = db.relationship('User', foreign_keys=[instructor_id], backref='instructor_lessons')


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='GBP')
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50), default='card')
    stripe_payment_intent_id = db.Column(db.String(255), unique=True, nullable=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('User', backref='payments')
    lesson = db.relationship('Lesson', backref='payment')


# Predefined driving skills for the checklist
DRIVING_SKILLS = [
    ('cockpit_drill', 'Cockpit Drill & Controls'),
    ('moving_off', 'Moving Off & Stopping'),
    ('steering', 'Steering Control'),
    ('gear_changing', 'Gear Changing'),
    ('junctions', 'Junctions & Crossroads'),
    ('roundabouts', 'Roundabouts'),
    ('parking_parallel', 'Parallel Parking'),
    ('parking_bay', 'Bay Parking'),
    ('parking_reverse', 'Reverse Parking'),
    ('hill_start', 'Hill Starts'),
    ('emergency_stop', 'Emergency Stop'),
    ('mirrors_signals', 'Mirror & Signal Use'),
    ('lane_discipline', 'Lane Discipline'),
    ('motorway_driving', 'Motorway Driving'),
    ('dual_carriageway', 'Dual Carriageway'),
    ('night_driving', 'Night Driving'),
    ('independent_driving', 'Independent Driving'),
    ('pedestrian_crossings', 'Pedestrian Crossings'),
    ('overtaking', 'Overtaking'),
    ('country_roads', 'Country Roads'),
]


class LessonFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(
        db.Integer, db.ForeignKey('lesson.id'), nullable=False, unique=True
    )
    instructor_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False
    )
    student_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False
    )
    rating = db.Column(db.Integer, default=3)  # 1-5
    notes = db.Column(db.Text)
    strengths = db.Column(db.Text)
    areas_to_improve = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lesson = db.relationship(
        'Lesson', backref=db.backref('feedback', uselist=False)
    )
    instructor = db.relationship(
        'User', foreign_keys=[instructor_id],
        backref='given_feedback'
    )
    student = db.relationship(
        'User', foreign_keys=[student_id],
        backref='received_feedback'
    )


class SkillProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False
    )
    skill_key = db.Column(db.String(50), nullable=False)
    status = db.Column(
        db.String(20), default='not_started'
    )  # not_started, in_progress, competent, mastered
    instructor_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True
    )
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    notes = db.Column(db.String(255))

    student = db.relationship(
        'User', foreign_keys=[student_id], backref='skill_progress'
    )
    instructor = db.relationship(
        'User', foreign_keys=[instructor_id]
    )

    __table_args__ = (
        db.UniqueConstraint(
            'student_id', 'skill_key', name='uq_student_skill'
        ),
    )


class LessonReschedule(db.Model):
    """Tracks rescheduling history for lessons."""
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    old_date = db.Column(db.Date, nullable=False)
    old_time = db.Column(db.Time, nullable=False)
    new_date = db.Column(db.Date, nullable=False)
    new_time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lesson = db.relationship('Lesson', backref='reschedule_history')
    requested_by = db.relationship('User', foreign_keys=[requested_by_id])


class Refund(db.Model):
    """Tracks refund requests and their processing status."""
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, processed
    stripe_refund_id = db.Column(db.String(255), nullable=True)
    processed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    payment = db.relationship('Payment', backref=db.backref('refunds', lazy='dynamic'))
    lesson = db.relationship('Lesson', backref='refund_requests')
    student = db.relationship('User', foreign_keys=[student_id], backref='refund_requests')
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])


# Block booking discount tiers
BLOCK_BOOKING_TIERS = [
    (5, 5, '5 Lessons – 5% Off'),
    (10, 10, '10 Lessons – 10% Off'),
    (20, 15, '20 Lessons – 15% Off'),
]


class BookingPackage(db.Model):
    """Stores purchased lesson packages with discount."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_lessons = db.Column(db.Integer, nullable=False)
    lessons_used = db.Column(db.Integer, default=0)
    price_per_lesson = db.Column(db.Float, nullable=False)
    discount_percent = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)
    payment_status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_id], backref='booking_packages')
    instructor = db.relationship('User', foreign_keys=[instructor_id], backref='instructor_packages')

    @property
    def lessons_remaining(self):
        return self.total_lessons - self.lessons_used


class InstructorReview(db.Model):
    """Public reviews left by students for instructors."""
    id = db.Column(db.Integer, primary_key=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    title = db.Column(db.String(100))
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    instructor = db.relationship('User', foreign_keys=[instructor_id], backref='received_reviews')
    student = db.relationship('User', foreign_keys=[student_id], backref='written_reviews')

    __table_args__ = (
        db.UniqueConstraint('instructor_id', 'student_id', name='uq_instructor_student_review'),
    )


class NotificationPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True
    )
    email_enabled = db.Column(db.Boolean, default=True)
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    notify_lesson_booked = db.Column(db.Boolean, default=True)
    notify_lesson_cancelled = db.Column(db.Boolean, default=True)
    notify_feedback = db.Column(db.Boolean, default=True)
    notify_payment = db.Column(db.Boolean, default=True)
    notify_skill_update = db.Column(db.Boolean, default=True)
    sms_enabled = db.Column(db.Boolean, default=False)

    user = db.relationship(
        'User',
        backref=db.backref('notification_pref', uselist=False)
    )


class InAppNotification(db.Model):
    """In-app notification shown in the notification bell."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), default='info')  # info, success, warning, danger
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='notifications')


class InstructorPayout(db.Model):
    """Tracks instructor payouts/earnings withdrawals."""
    id = db.Column(db.Integer, primary_key=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='GBP')
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)
    lessons_count = db.Column(db.Integer, default=0)
    stripe_transfer_id = db.Column(db.String(255), nullable=True)
    stripe_connect_account_id = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.String(255))
    processed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    instructor = db.relationship('User', foreign_keys=[instructor_id], backref='payouts')
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])
