from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Lesson, StudentProfile
from app.forms import BookLessonForm, StudentProfileForm

bp = Blueprint('student', __name__)

@bp.route('/student/dashboard')
@login_required
def dashboard():
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    lessons = Lesson.query.filter_by(student_id=current_user.id).all()
    return render_template('student/dashboard.html', lessons=lessons)

@bp.route('/student/book', methods=['GET', 'POST'])
@login_required
def book_lesson():
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    form = BookLessonForm()
    instructors = User.query.filter_by(role='instructor').all()
    if form.validate_on_submit():
        # Validate that the selected instructor exists and is an instructor
        instructor = User.query.filter_by(id=form.instructor_id.data, role='instructor').first()
        if not instructor:
            flash('Invalid instructor selected.')
            return redirect(url_for('student.book_lesson'))
        
        lesson = Lesson(
            student_id=current_user.id,
            instructor_id=form.instructor_id.data,
            date=form.date.data,
            time=form.time.data,
            duration=form.duration.data * 60,  # Convert hours to minutes
            status='confirmed'
        )
        db.session.add(lesson)
        db.session.commit()
        flash('Lesson booked successfully!')
        return redirect(url_for('student.dashboard'))
    return render_template('student/book_lesson.html', form=form, instructors=instructors)

@bp.route('/student/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    # Create profile if it doesn't exist
    if not current_user.student_profile:
        profile = StudentProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()
    form = StudentProfileForm()
    if form.validate_on_submit():
        current_user.student_profile.phone = form.phone.data
        db.session.commit()
        flash('Profile updated.')
        return redirect(url_for('student.profile'))
    elif request.method == 'GET':
        form.phone.data = current_user.student_profile.phone
    return render_template('student/profile.html', form=form)