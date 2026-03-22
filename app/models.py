from app import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='student')  # admin, instructor, student

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