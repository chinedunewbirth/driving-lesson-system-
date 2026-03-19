from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from app import db
from app.models import Lesson, InstructorProfile, User, StudentProfile
from app.forms import InstructorProfileForm, InstructorRegisterStudentForm

bp = Blueprint('instructor', __name__)

@bp.route('/instructor/dashboard')
@login_required
def dashboard():
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    lessons = Lesson.query.filter_by(instructor_id=current_user.id).all()
    return render_template('instructor/dashboard.html', lessons=lessons)

@bp.route('/instructor/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    if not current_user.instructor_profile:
        profile = InstructorProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()
    form = InstructorProfileForm()
    if form.validate_on_submit():
        current_user.instructor_profile.bio = form.bio.data
        current_user.instructor_profile.hourly_rate = form.hourly_rate.data
        db.session.commit()
        flash('Profile updated.')
        return redirect(url_for('instructor.profile'))
    elif request.method == 'GET':
        form.bio.data = current_user.instructor_profile.bio
        form.hourly_rate.data = current_user.instructor_profile.hourly_rate
    return render_template('instructor/profile.html', form=form)

@bp.route('/instructor/register-student', methods=['GET', 'POST'])
@login_required
def register_student():
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    form = InstructorRegisterStudentForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role='student')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        profile = StudentProfile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()
        flash('Student registered successfully!')
        return redirect(url_for('instructor.dashboard'))
    return render_template('instructor/register_student.html', form=form)