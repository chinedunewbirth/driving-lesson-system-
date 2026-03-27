from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, SelectField, DateField,
    TimeField, IntegerField, TextAreaField, FloatField, HiddenField,
    BooleanField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, ValidationError, Optional
)
from app.models import User


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField(
        'Role',
        choices=[('instructor', 'Instructor'), ('student', 'Student')],
        validators=[DataRequired()]
    )
    address_line1 = StringField('Address Line 1', validators=[Optional()])
    address_line2 = StringField('Address Line 2', validators=[Optional()])
    city = StringField('City / Town', validators=[Optional()])
    county = StringField('County', validators=[Optional()])
    postcode = StringField('Postcode', validators=[Optional()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')


class InstructorRegisterStudentForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    location = StringField('Location', validators=[Optional()])
    submit = SubmitField('Register Student')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')


class InstructorProfileForm(FlaskForm):
    bio = TextAreaField('Bio', validators=[DataRequired()])
    hourly_rate = FloatField('Hourly Rate (£)', validators=[DataRequired()])
    address = StringField('Service Area Address', validators=[Optional()])
    latitude = HiddenField('Latitude')
    longitude = HiddenField('Longitude')
    service_radius_km = FloatField('Service Radius (km)', validators=[Optional()], default=15.0)
    submit = SubmitField('Save')


class StudentProfileForm(FlaskForm):
    phone = StringField('Phone Number', validators=[DataRequired()])
    submit = SubmitField('Save')


class BookLessonForm(FlaskForm):
    instructor_id = IntegerField('Instructor', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    time = TimeField('Time', validators=[DataRequired()])
    duration = IntegerField('Duration (hours)', validators=[DataRequired()])
    pickup_address = StringField('Pickup Address', validators=[Optional()])
    pickup_lat = HiddenField('Pickup Latitude')
    pickup_lng = HiddenField('Pickup Longitude')
    submit = SubmitField('Book Lesson')


class ChatbotForm(FlaskForm):
    message = StringField('Your message', validators=[DataRequired()])
    submit = SubmitField('Send')


class PaymentForm(FlaskForm):
    """Form for payment processing via Stripe"""
    card_holder_name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    amount = FloatField('Lesson Fee (USD)', validators=[DataRequired()])
    submit = SubmitField('Proceed to Payment')


class LessonFeedbackForm(FlaskForm):
    """Instructor feedback after a completed lesson"""
    rating = SelectField(
        'Overall Rating',
        choices=[
            ('1', '1 - Needs Significant Work'),
            ('2', '2 - Below Average'),
            ('3', '3 - Average'),
            ('4', '4 - Good'),
            ('5', '5 - Excellent'),
        ],
        validators=[DataRequired()]
    )
    notes = TextAreaField('Session Notes', validators=[DataRequired()])
    strengths = TextAreaField('Strengths', validators=[Optional()])
    areas_to_improve = TextAreaField(
        'Areas to Improve', validators=[Optional()]
    )
    submit = SubmitField('Submit Feedback')


class SkillUpdateForm(FlaskForm):
    """Update a student's skill status"""
    skill_key = HiddenField(validators=[DataRequired()])
    status = SelectField(
        'Status',
        choices=[
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('competent', 'Competent'),
            ('mastered', 'Mastered'),
        ],
        validators=[DataRequired()]
    )
    notes = StringField('Notes', validators=[Optional()])
    submit = SubmitField('Update')


class NotificationPreferenceForm(FlaskForm):
    """Notification preference settings"""
    email_enabled = BooleanField('Email Notifications')
    whatsapp_enabled = BooleanField('WhatsApp Notifications')
    sms_enabled = BooleanField('SMS Notifications')
    phone = StringField('Phone Number (with country code, e.g. +44...)',
                        validators=[Optional()])
    notify_lesson_booked = BooleanField('Lesson Booked')
    notify_lesson_cancelled = BooleanField('Lesson Cancelled')
    notify_feedback = BooleanField('Feedback Received')
    notify_payment = BooleanField('Payment Confirmation')
    notify_skill_update = BooleanField('Skill Updates')
    submit = SubmitField('Save Preferences')


class RescheduleLessonForm(FlaskForm):
    """Reschedule an existing lesson to a new date/time"""
    new_date = DateField('New Date', validators=[DataRequired()])
    new_time = TimeField('New Time', validators=[DataRequired()])
    reason = TextAreaField('Reason for Rescheduling', validators=[Optional()])
    submit = SubmitField('Reschedule Lesson')


class RefundRequestForm(FlaskForm):
    """Request a refund for a paid lesson"""
    reason = TextAreaField('Reason for Refund', validators=[DataRequired()])
    submit = SubmitField('Submit Refund Request')


class RefundProcessForm(FlaskForm):
    """Admin form to approve/reject a refund"""
    action = SelectField(
        'Decision',
        choices=[('approved', 'Approve Refund'), ('rejected', 'Reject Refund')],
        validators=[DataRequired()]
    )
    submit = SubmitField('Process Refund')


class BlockBookingForm(FlaskForm):
    """Purchase a block of lessons at a discount"""
    instructor_id = IntegerField('Instructor', validators=[DataRequired()])
    package_tier = SelectField(
        'Package',
        choices=[('5', '5 Lessons – 5% Off'), ('10', '10 Lessons – 10% Off'), ('20', '20 Lessons – 15% Off')],
        validators=[DataRequired()]
    )
    submit = SubmitField('Purchase Package')


class InstructorReviewForm(FlaskForm):
    """Student review for an instructor"""
    rating = SelectField(
        'Rating',
        choices=[
            ('5', '5 - Excellent'),
            ('4', '4 - Very Good'),
            ('3', '3 - Good'),
            ('2', '2 - Fair'),
            ('1', '1 - Poor'),
        ],
        validators=[DataRequired()]
    )
    title = StringField('Review Title', validators=[DataRequired()])
    comment = TextAreaField('Your Review', validators=[DataRequired()])
    submit = SubmitField('Submit Review')
