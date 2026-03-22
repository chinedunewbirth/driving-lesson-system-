from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Lesson, InstructorProfile, InstructorAvailability, User, StudentProfile
from app.forms import InstructorProfileForm, InstructorRegisterStudentForm
from datetime import time as dt_time

bp = Blueprint('instructor', __name__)

@bp.route('/instructor/dashboard')
@login_required
def dashboard():
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    lessons = Lesson.query.filter_by(instructor_id=current_user.id).all()
    cancelled_lessons = [
        l for l in lessons if l.status == 'cancelled'
    ]
    return render_template('instructor/dashboard.html', lessons=lessons, cancelled_lessons=cancelled_lessons)

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
        p = current_user.instructor_profile
        p.bio = form.bio.data
        p.hourly_rate = form.hourly_rate.data
        p.address = form.address.data
        if form.latitude.data:
            try:
                p.latitude = float(form.latitude.data)
            except (ValueError, TypeError):
                pass
        if form.longitude.data:
            try:
                p.longitude = float(form.longitude.data)
            except (ValueError, TypeError):
                pass
        if form.service_radius_km.data:
            p.service_radius_km = form.service_radius_km.data
        db.session.commit()
        flash('Profile updated.')
        return redirect(url_for('instructor.profile'))
    elif request.method == 'GET':
        p = current_user.instructor_profile
        form.bio.data = p.bio
        form.hourly_rate.data = p.hourly_rate
        form.address.data = p.address
        form.latitude.data = p.latitude
        form.longitude.data = p.longitude
        form.service_radius_km.data = p.service_radius_km or 15.0
    availability = InstructorAvailability.query.filter_by(
        instructor_id=current_user.id
    ).order_by(InstructorAvailability.day_of_week, InstructorAvailability.start_time).all()
    lessons = Lesson.query.filter_by(instructor_id=current_user.id).all()
    return render_template('instructor/profile.html', form=form, availability=availability, lessons=lessons)

@bp.route('/instructor/cancel/<int:lesson_id>', methods=['POST'])
@login_required
def cancel_lesson(lesson_id):
    """Instructor cancels a lesson"""
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    lesson = Lesson.query.get_or_404(lesson_id)

    if lesson.instructor_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('instructor.dashboard'))

    if lesson.status != 'confirmed':
        flash('This lesson cannot be cancelled.', 'warning')
        return redirect(url_for('instructor.dashboard'))

    lesson.status = 'cancelled'
    db.session.commit()
    flash('Lesson cancelled successfully.', 'success')
    return redirect(url_for('instructor.dashboard'))


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


@bp.route('/instructor/availability', methods=['POST'])
@login_required
def save_availability():
    """Save weekly availability slots."""
    if not current_user.is_instructor():
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if not data or 'slots' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    # Clear existing availability
    InstructorAvailability.query.filter_by(instructor_id=current_user.id).delete()

    for slot in data['slots']:
        day = int(slot.get('day', 0))
        start = slot.get('start', '')
        end = slot.get('end', '')
        if not start or not end or day < 0 or day > 6:
            continue
        try:
            sh, sm = map(int, start.split(':'))
            eh, em = map(int, end.split(':'))
        except (ValueError, AttributeError):
            continue
        if sh >= eh and not (eh == 0 and em == 0):
            continue
        avail = InstructorAvailability(
            instructor_id=current_user.id,
            day_of_week=day,
            start_time=dt_time(sh, sm),
            end_time=dt_time(eh, em)
        )
        db.session.add(avail)

    db.session.commit()
    return jsonify({'success': True})


@bp.route('/instructor/availability', methods=['GET'])
@login_required
def get_availability():
    """Get own availability as JSON."""
    if not current_user.is_instructor():
        return jsonify({'error': 'Access denied'}), 403
    slots = InstructorAvailability.query.filter_by(
        instructor_id=current_user.id
    ).order_by(InstructorAvailability.day_of_week, InstructorAvailability.start_time).all()
    return jsonify({'slots': [
        {'day': s.day_of_week, 'start': s.start_time.strftime('%H:%M'), 'end': s.end_time.strftime('%H:%M')}
        for s in slots
    ]})