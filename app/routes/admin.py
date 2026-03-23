from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import (
    User, Lesson, InstructorProfile, StudentProfile, Payment,
    LessonFeedback, SkillProgress, InstructorAvailability, NotificationPreference,
    Refund, BookingPackage, InstructorPayout
)
from app import db
from sqlalchemy import func, extract
from datetime import datetime, date, timedelta
from functools import wraps
import calendar
import stripe
import logging
from app.notifications import notify_user

logger = logging.getLogger(__name__)

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
    instructor_stats = (
        db.session.query(
            User.id, User.username,
            InstructorProfile.hourly_rate,
            func.count(Lesson.id).label('total_lessons'),
            func.sum(db.case((Lesson.status == 'completed', 1), else_=0)).label('completed'),
            func.sum(db.case((Lesson.status == 'cancelled', 1), else_=0)).label('cancelled'),
            func.sum(db.case(
                (Lesson.status == 'completed', Lesson.duration), else_=0
            )).label('total_minutes')
        )
        .join(InstructorProfile, User.id == InstructorProfile.user_id)
        .outerjoin(Lesson, User.id == Lesson.instructor_id)
        .filter(User.role == 'instructor')
        .group_by(User.id, User.username, InstructorProfile.hourly_rate)
        .all()
    )

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
    student_stats = (
        db.session.query(
            User.id, User.username, User.email,
            func.count(Lesson.id).label('total_lessons'),
            func.sum(db.case((Lesson.status == 'completed', 1), else_=0)).label('completed'),
            func.sum(db.case((Lesson.status == 'confirmed', 1), else_=0)).label('upcoming'),
            func.sum(db.case((Lesson.status == 'cancelled', 1), else_=0)).label('cancelled'),
            func.sum(db.case(
                (Lesson.status == 'completed', Lesson.duration), else_=0
            )).label('total_minutes')
        )
        .outerjoin(Lesson, User.id == Lesson.student_id)
        .filter(User.role == 'student')
        .group_by(User.id, User.username, User.email)
        .all()
    )

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

    return render_template(
        'admin/dashboard.html',
        users=users, lessons=lessons, payments=payments,
        instructors=instructors, students=students,
        total_revenue=total_revenue, today_lessons=today_lessons,
        monthly_data=monthly_data, monthly_revenue=monthly_revenue,
        status_dist=status_dist
    )


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

    # Delete related feedback
    LessonFeedback.query.filter(
        (LessonFeedback.instructor_id == user_id) | (LessonFeedback.student_id == user_id)
    ).delete(synchronize_session=False)

    # Delete related skill progress
    SkillProgress.query.filter(
        (SkillProgress.student_id == user_id) | (SkillProgress.instructor_id == user_id)
    ).delete(synchronize_session=False)

    # Delete related availability
    InstructorAvailability.query.filter_by(instructor_id=user_id).delete(synchronize_session=False)

    # Delete notification preferences
    NotificationPreference.query.filter_by(user_id=user_id).delete(synchronize_session=False)

    # Delete related lessons
    Lesson.query.filter(
        (Lesson.student_id == user_id) | (Lesson.instructor_id == user_id)
    ).delete(synchronize_session=False)
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


# ── Refund Management ──────────────────────────────────────
@bp.route('/admin/refunds')
@admin_required
def refunds():
    """View all refund requests"""
    all_refunds = Refund.query.order_by(Refund.created_at.desc()).all()
    return render_template('admin/refunds.html', refunds=all_refunds)


@bp.route('/admin/refunds/<int:refund_id>/process', methods=['POST'])
@admin_required
def process_refund(refund_id):
    """Approve or reject a refund request"""
    refund = Refund.query.get_or_404(refund_id)

    if refund.status != 'pending':
        flash('This refund has already been processed.', 'warning')
        return redirect(url_for('admin.refunds'))

    action = request.form.get('action', '').strip()
    if action not in ('approved', 'rejected'):
        flash('Invalid action.', 'danger')
        return redirect(url_for('admin.refunds'))

    refund.status = action
    refund.processed_by_id = current_user.id
    refund.processed_at = datetime.utcnow()

    if action == 'approved':
        # Attempt Stripe refund if payment has a PaymentIntent
        payment = Payment.query.get(refund.payment_id)
        if payment and payment.stripe_payment_intent_id:
            try:
                stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                stripe_refund = stripe.Refund.create(
                    payment_intent=payment.stripe_payment_intent_id,
                    amount=int(refund.amount * 100)
                )
                refund.stripe_refund_id = stripe_refund.id
                refund.status = 'processed'
            except stripe.error.StripeError as e:
                logger.error(f'Stripe refund error: {e}')
                flash(f'Stripe refund failed: {e}. Refund marked as approved for manual processing.', 'warning')

        if payment:
            payment.status = 'refunded'

    db.session.commit()

    # Notify student
    student = User.query.get(refund.student_id)
    if student:
        notify_user(student, 'refund_processed', **{
            'student_name': student.username,
            'amount': f'{refund.amount:.2f}',
            'status': action,
        })

    flash(f'Refund {action} successfully.', 'success')
    return redirect(url_for('admin.refunds'))


# ── Payouts ────────────────────────────────────────────────
@bp.route('/admin/payouts')
@admin_required
def payouts():
    """View all instructor payout requests."""
    status_filter = request.args.get('status', 'all')
    query = InstructorPayout.query.order_by(InstructorPayout.created_at.desc())
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    all_payouts = query.all()

    stats = {
        'total_pending': db.session.query(func.coalesce(func.sum(InstructorPayout.amount), 0)).filter_by(status='pending').scalar(),
        'total_completed': db.session.query(func.coalesce(func.sum(InstructorPayout.amount), 0)).filter_by(status='completed').scalar(),
        'pending_count': InstructorPayout.query.filter_by(status='pending').count(),
    }
    return render_template('admin/payouts.html', payouts=all_payouts, stats=stats, status_filter=status_filter)


@bp.route('/admin/payouts/<int:payout_id>/process', methods=['POST'])
@admin_required
def process_payout(payout_id):
    """Approve/process or reject a payout request."""
    payout = InstructorPayout.query.get_or_404(payout_id)

    if payout.status != 'pending':
        flash('This payout has already been processed.', 'warning')
        return redirect(url_for('admin.payouts'))

    action = request.form.get('action', '').strip()
    if action not in ('completed', 'failed'):
        flash('Invalid action.', 'danger')
        return redirect(url_for('admin.payouts'))

    payout.status = action
    payout.processed_by_id = current_user.id
    payout.processed_at = datetime.utcnow()
    payout.notes = request.form.get('notes', '').strip()

    if action == 'completed' and payout.stripe_connect_account_id:
        try:
            stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
            transfer = stripe.Transfer.create(
                amount=int(payout.amount * 100),
                currency='gbp',
                destination=payout.stripe_connect_account_id,
                description=f'DriveSmart payout #{payout.id}',
            )
            payout.stripe_transfer_id = transfer.id
        except stripe.error.StripeError as e:
            logger.error(f'Stripe transfer error: {e}')
            flash(f'Stripe transfer failed: {e}. Payout marked as completed for manual processing.', 'warning')

    db.session.commit()

    # Notify instructor
    instructor = User.query.get(payout.instructor_id)
    if instructor:
        notify_user(instructor, 'payout_processed', **{
            'instructor_name': instructor.username,
            'amount': f'{payout.amount:.2f}',
            'status': action,
            'period_start': str(payout.period_start or ''),
            'period_end': str(payout.period_end or ''),
            'lessons_count': payout.lessons_count or 0,
            'notes': payout.notes or '',
        })

    flash(f'Payout {action} successfully.', 'success')
    return redirect(url_for('admin.payouts'))
