from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import User, Lesson, InstructorProfile, StudentProfile, Payment
from app import db
from sqlalchemy import func, extract
from datetime import datetime, date, timedelta
from functools import wraps
import calendar

bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash('Access denied: Admins only.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ──────────────────────────────────────────────
@bp.route('/admin/dashboard')
@admin_required
def dashboard():
    users = User.query.all()
    lessons = Lesson.query.all()
    payments = Payment.query.all()

    # Instructor performance stats
    instructor_stats = db.session.query(
        User.id, User.username,
        InstructorProfile.hourly_rate,
        func.count(Lesson.id).label('total_lessons'),
        func.sum(db.case((Lesson.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(db.case((Lesson.status == 'cancelled', 1), else_=0)).label('cancelled'),
        func.sum(db.case((Lesson.status == 'completed', Lesson.duration), else_=0)).label('total_minutes')
    ).join(InstructorProfile, User.id == InstructorProfile.user_id
    ).outerjoin(Lesson, User.id == Lesson.instructor_id
    ).filter(User.role == 'instructor'
    ).group_by(User.id, User.username, InstructorProfile.hourly_rate).all()

    instructors = []
    for i in instructor_stats:
        total = i.total_lessons or 0
        completed = i.completed or 0
        mins = i.total_minutes or 0
        rate = i.hourly_rate or 0
        instructors.append({
            'id': i.id, 'username': i.username, 'hourly_rate': rate,
            'total_lessons': total, 'completed': completed,
            'cancelled': i.cancelled or 0,
            'hours': round(mins / 60, 1),
            'earnings': round((mins / 60) * rate, 2),
            'rate': round(completed / total * 100) if total > 0 else 0
        })

    # Student progress stats
    student_stats = db.session.query(
        User.id, User.username, User.email,
        func.count(Lesson.id).label('total_lessons'),
        func.sum(db.case((Lesson.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(db.case((Lesson.status == 'confirmed', 1), else_=0)).label('upcoming'),
        func.sum(db.case((Lesson.status == 'cancelled', 1), else_=0)).label('cancelled'),
        func.sum(db.case((Lesson.status == 'completed', Lesson.duration), else_=0)).label('total_minutes')
    ).outerjoin(Lesson, User.id == Lesson.student_id
    ).filter(User.role == 'student'
    ).group_by(User.id, User.username, User.email).all()

    students = []
    for s in student_stats:
        students.append({
            'id': s.id, 'username': s.username, 'email': s.email,
            'total_lessons': s.total_lessons or 0,
            'completed': s.completed or 0,
            'upcoming': s.upcoming or 0,
            'cancelled': s.cancelled or 0,
            'hours': round((s.total_minutes or 0) / 60, 1)
        })

    # Revenue
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(Payment.status == 'completed').scalar() or 0

    # Today's lessons
    today_lessons = Lesson.query.filter(Lesson.date == date.today()).count()

    # Monthly lesson stats for charts (last 6 months)
    monthly_data = []
    today = date.today()
    for i in range(5, -1, -1):
        m_date = today.replace(day=1) - timedelta(days=i * 28)
        m_year, m_month = m_date.year, m_date.month
        month_lessons = db.session.query(
            func.count(Lesson.id).label('total'),
            func.sum(db.case((Lesson.status == 'completed', 1), else_=0)).label('completed'),
            func.sum(db.case((Lesson.status == 'confirmed', 1), else_=0)).label('confirmed'),
            func.sum(db.case((Lesson.status == 'cancelled', 1), else_=0)).label('cancelled')
        ).filter(
            extract('year', Lesson.date) == m_year,
            extract('month', Lesson.date) == m_month
        ).first()
        monthly_data.append({
            'label': calendar.month_abbr[m_month] + ' ' + str(m_year)[-2:],
            'total': month_lessons.total or 0,
            'completed': month_lessons.completed or 0,
            'confirmed': month_lessons.confirmed or 0,
            'cancelled': month_lessons.cancelled or 0
        })

    # Monthly revenue for chart
    monthly_revenue = []
    for i in range(5, -1, -1):
        m_date = today.replace(day=1) - timedelta(days=i * 28)
        m_year, m_month = m_date.year, m_date.month
        rev = db.session.query(
            func.sum(Payment.amount)
        ).filter(
            Payment.status == 'completed',
            extract('year', Payment.created_at) == m_year,
            extract('month', Payment.created_at) == m_month
        ).scalar() or 0
        monthly_revenue.append(round(rev, 2))

    # Lesson status distribution
    status_counts = db.session.query(
        Lesson.status, func.count(Lesson.id)
    ).group_by(Lesson.status).all()
    status_dist = {s: c for s, c in status_counts}

    return render_template('admin/dashboard.html',
        users=users, lessons=lessons, payments=payments,
        instructors=instructors, students=students,
        total_revenue=total_revenue, today_lessons=today_lessons,
        monthly_data=monthly_data, monthly_revenue=monthly_revenue,
        status_dist=status_dist)


# ── User Management ────────────────────────────────────────
@bp.route('/admin/users')
@admin_required
def users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@bp.route('/admin/users/add', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', '').strip()
    password = request.form.get('password', '')

    if not all([username, email, role, password]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.users'))

    if role not in ('student', 'instructor', 'admin'):
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'danger')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(email=email).first():
        flash('Email already exists.', 'danger')
        return redirect(url_for('admin.users'))

    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)

    if role == 'instructor':
        hourly_rate = request.form.get('hourly_rate', 30.0, type=float)
        profile = InstructorProfile(user=user, bio='', hourly_rate=hourly_rate)
        db.session.add(profile)
    elif role == 'student':
        phone = request.form.get('phone', '').strip()
        profile = StudentProfile(user=user, phone=phone)
        db.session.add(profile)

    db.session.commit()
    flash(f'User "{username}" created successfully.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', '').strip()

    if not all([username, email, role]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.users'))

    if role not in ('student', 'instructor', 'admin'):
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.users'))

    existing = User.query.filter_by(username=username).first()
    if existing and existing.id != user_id:
        flash('Username already taken.', 'danger')
        return redirect(url_for('admin.users'))

    existing = User.query.filter_by(email=email).first()
    if existing and existing.id != user_id:
        flash('Email already taken.', 'danger')
        return redirect(url_for('admin.users'))

    user.username = username
    user.email = email
    user.role = role
    db.session.commit()
    flash(f'User "{username}" updated successfully.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.users'))

    user = User.query.get_or_404(user_id)
    username = user.username

    # Delete related profiles
    if user.instructor_profile:
        db.session.delete(user.instructor_profile)
    if user.student_profile:
        db.session.delete(user.student_profile)

    # Delete related lessons
    Lesson.query.filter((Lesson.student_id == user_id) | (Lesson.instructor_id == user_id)).delete(synchronize_session=False)
    # Delete related payments
    Payment.query.filter_by(student_id=user_id).delete(synchronize_session=False)

    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" deleted successfully.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '')
    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin.users'))
    user.set_password(new_password)
    db.session.commit()
    flash(f'Password reset for "{user.username}".', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/admin/users/<int:user_id>/change-role', methods=['POST'])
@admin_required
def change_role(user_id):
    if user_id == current_user.id:
        flash('You cannot change your own role.', 'danger')
        return redirect(url_for('admin.users'))

    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', '').strip()
    if new_role not in ('student', 'instructor', 'admin'):
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.users'))

    user.role = new_role
    # Create profile if changing to instructor/student
    if new_role == 'instructor' and not user.instructor_profile:
        db.session.add(InstructorProfile(user=user, bio='', hourly_rate=30.0))
    elif new_role == 'student' and not user.student_profile:
        db.session.add(StudentProfile(user=user, phone=''))

    db.session.commit()
    flash(f'Role changed to "{new_role}" for "{user.username}".', 'success')
    return redirect(url_for('admin.users'))


# ── Lesson Management ──────────────────────────────────────
@bp.route('/admin/lessons')
@admin_required
def lessons():
    lessons = Lesson.query.order_by(Lesson.date.desc(), Lesson.time.desc()).all()
    users = User.query.all()
    return render_template('admin/lessons.html', lessons=lessons, users=users)


@bp.route('/admin/lessons/add', methods=['POST'])
@admin_required
def add_lesson():
    student_id = request.form.get('student_id', type=int)
    instructor_id = request.form.get('instructor_id', type=int)
    lesson_date = request.form.get('date', '')
    lesson_time = request.form.get('time', '')
    duration = request.form.get('duration', type=float)

    if not all([student_id, instructor_id, lesson_date, lesson_time, duration]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.lessons'))

    student = User.query.get(student_id)
    instructor = User.query.get(instructor_id)
    if not student or not instructor:
        flash('Invalid student or instructor.', 'danger')
        return redirect(url_for('admin.lessons'))

    lesson = Lesson(
        student_id=student_id,
        instructor_id=instructor_id,
        date=datetime.strptime(lesson_date, '%Y-%m-%d').date(),
        time=datetime.strptime(lesson_time, '%H:%M').time(),
        duration=int(duration * 60),
        status='confirmed'
    )
    db.session.add(lesson)
    db.session.commit()
    flash('Lesson scheduled successfully.', 'success')
    return redirect(url_for('admin.lessons'))


@bp.route('/admin/lessons/<int:lesson_id>/complete', methods=['POST'])
@admin_required
def complete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.status != 'confirmed':
        flash('Only confirmed lessons can be completed.', 'warning')
        return redirect(url_for('admin.lessons'))
    lesson.status = 'completed'
    db.session.commit()
    flash('Lesson marked as completed.', 'success')
    return redirect(url_for('admin.lessons'))


@bp.route('/admin/lessons/<int:lesson_id>/cancel', methods=['POST'])
@admin_required
def cancel_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.status != 'confirmed':
        flash('Only confirmed lessons can be cancelled.', 'warning')
        return redirect(url_for('admin.lessons'))
    lesson.status = 'cancelled'
    db.session.commit()
    flash('Lesson cancelled.', 'success')
    return redirect(url_for('admin.lessons'))


@bp.route('/admin/lessons/<int:lesson_id>/delete', methods=['POST'])
@admin_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    Payment.query.filter_by(lesson_id=lesson_id).delete(synchronize_session=False)
    db.session.delete(lesson)
    db.session.commit()
    flash('Lesson deleted.', 'success')
    return redirect(url_for('admin.lessons'))