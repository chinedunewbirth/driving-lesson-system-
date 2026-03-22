from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField, TimeField, IntegerField, TextAreaField, FloatField, RadioField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional
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
    role = SelectField('Role', choices=[('instructor', 'Instructor'), ('student', 'Student')], validators=[DataRequired()])
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