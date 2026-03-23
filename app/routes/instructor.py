from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    Lesson, InstructorProfile, InstructorAvailability,
    User, StudentProfile, LessonFeedback, SkillProgress, DRIVING_SKILLS,
    Payment, InstructorPayout
)
from app.forms import (
    InstructorProfileForm, InstructorRegisterStudentForm,
    LessonFeedbackForm, SkillUpdateForm
)
from datetime import datetime, date, time as dt_time, timedelta
from app.notifications import notify_user
from sqlalchemy import func, extract
import calendar

bp = Blueprint('instructor', __name__)


@bp.route('/instructor/dashboard')
@login_required
def dashboard():
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    lessons = Lesson.query.filter_by(instructor_id=current_user.id).all()
    cancelled_lessons = [
        les for les in lessons if les.status == 'cancelled'
    ]

    # Revenue data: payments linked to this instructor's lessons
    instructor_payments = (
        db.session.query(Payment)
        .join(Lesson, Payment.lesson_id == Lesson.id)
        .filter(Lesson.instructor_id == current_user.id)
        .all()
    )

    total_revenue = sum(p.amount for p in instructor_payments if p.status == 'completed')
    pending_revenue = sum(p.amount for p in instructor_payments if p.status == 'pending')

    # Monthly revenue for last 6 months
    today = date.today()
    monthly_revenue = []
    for i in range(5, -1, -1):
        m_date = today.replace(day=1) - timedelta(days=i * 28)
        m_year, m_month = m_date.year, m_date.month
        rev = (
            db.session.query(func.coalesce(func.sum(Payment.amount), 0))
            .join(Lesson, Payment.lesson_id == Lesson.id)
            .filter(
                Lesson.instructor_id == current_user.id,
                Payment.status == 'completed',
                extract('year', Payment.created_at) == m_year,
                extract('month', Payment.created_at) == m_month,
            )
            .scalar()
        ) or 0
        monthly_revenue.append({
            'label': calendar.month_abbr[m_month],
            'amount': round(float(rev), 2),
        })

    # Recent payments
    recent_payments = (
        db.session.query(Payment, User.username)
        .join(Lesson, Payment.lesson_id == Lesson.id)
        .join(User, Payment.student_id == User.id)
        .filter(Lesson.instructor_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        'instructor/dashboard.html',
        lessons=lessons,
        cancelled_lessons=cancelled_lessons,
        total_revenue=total_revenue,
        pending_revenue=pending_revenue,
        monthly_revenue=monthly_revenue,
        recent_payments=recent_payments,
    )


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

    # Notify student about instructor cancellation
    student = User.query.get(lesson.student_id)
    if student:
        notify_user(student, 'lesson_cancelled', **{
            'recipient_name': student.username,
            'cancelled_by': current_user.username,
            'date': lesson.date.strftime('%b %d, %Y') if lesson.date else 'N/A',
            'time': lesson.time.strftime('%I:%M %p') if lesson.time else 'N/A',
        })

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
        profile = StudentProfile(user_id=user.id, address=form.location.data)
        db.session.add(profile)
        db.session.commit()

        # Send welcome notification to new student
        notify_user(user, 'welcome', **{
            'username': user.username,
            'role': 'Student',
            'email': user.email,
            'login_url': url_for('auth.login', _external=True),
        })

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


@bp.route('/instructor/feedback/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
def lesson_feedback(lesson_id):
    """Submit feedback for a completed lesson."""
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.instructor_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('instructor.dashboard'))

    if lesson.status != 'completed':
        flash('Feedback can only be given for completed lessons.', 'warning')
        return redirect(url_for('instructor.dashboard'))

    existing = LessonFeedback.query.filter_by(lesson_id=lesson_id).first()
    if existing:
        flash('Feedback already submitted for this lesson.', 'info')
        return redirect(url_for('instructor.dashboard'))

    form = LessonFeedbackForm()
    if form.validate_on_submit():
        feedback = LessonFeedback(
            lesson_id=lesson_id,
            instructor_id=current_user.id,
            student_id=lesson.student_id,
            rating=int(form.rating.data),
            notes=form.notes.data,
            strengths=form.strengths.data,
            areas_to_improve=form.areas_to_improve.data
        )
        db.session.add(feedback)
        db.session.commit()

        # Notify student about new feedback
        student = User.query.get(lesson.student_id)
        if student:
            notify_user(student, 'feedback_received', **{
                'student_name': student.username,
                'instructor_name': current_user.username,
                'date': lesson.date.strftime('%b %d, %Y') if lesson.date else 'N/A',
                'rating': int(form.rating.data),
                'notes': form.notes.data or '',
                'strengths': form.strengths.data or '',
                'areas_to_improve': form.areas_to_improve.data or '',
            })

        flash('Feedback submitted successfully!', 'success')
        return redirect(url_for('instructor.dashboard'))

    return render_template(
        'instructor/feedback.html', form=form, lesson=lesson
    )


@bp.route('/instructor/student/<int:student_id>/skills')
@login_required
def student_skills(student_id):
    """View and manage a student's skill checklist."""
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    student = User.query.get_or_404(student_id)
    if not student.is_student():
        flash('Invalid student.', 'danger')
        return redirect(url_for('instructor.dashboard'))

    # Verify instructor teaches this student
    has_lessons = Lesson.query.filter_by(
        instructor_id=current_user.id, student_id=student_id
    ).first()
    if not has_lessons:
        flash('You have no lessons with this student.', 'danger')
        return redirect(url_for('instructor.dashboard'))

    # Get existing progress
    progress_map = {}
    records = SkillProgress.query.filter_by(
        student_id=student_id
    ).all()
    for r in records:
        progress_map[r.skill_key] = r

    skills = []
    for key, label in DRIVING_SKILLS:
        prog = progress_map.get(key)
        skills.append({
            'key': key,
            'label': label,
            'status': prog.status if prog else 'not_started',
            'notes': prog.notes if prog else '',
        })

    form = SkillUpdateForm()
    return render_template(
        'instructor/student_skills.html',
        student=student, skills=skills, form=form
    )


@bp.route(
    '/instructor/student/<int:student_id>/skills/update',
    methods=['POST']
)
@login_required
def update_student_skill(student_id):
    """Update a single skill for a student."""
    if not current_user.is_instructor():
        return jsonify({'error': 'Access denied'}), 403

    student = User.query.get_or_404(student_id)
    if not student.is_student():
        return jsonify({'error': 'Invalid student'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data'}), 400

    skill_key = data.get('skill_key', '')
    status = data.get('status', '')
    notes = data.get('notes', '')

    valid_keys = [k for k, _ in DRIVING_SKILLS]
    valid_statuses = [
        'not_started', 'in_progress', 'competent', 'mastered'
    ]
    if skill_key not in valid_keys or status not in valid_statuses:
        return jsonify({'error': 'Invalid skill or status'}), 400

    prog = SkillProgress.query.filter_by(
        student_id=student_id, skill_key=skill_key
    ).first()

    if prog:
        prog.status = status
        prog.notes = notes
        prog.instructor_id = current_user.id
    else:
        prog = SkillProgress(
            student_id=student_id,
            skill_key=skill_key,
            status=status,
            notes=notes,
            instructor_id=current_user.id
        )
        db.session.add(prog)

    db.session.commit()

    # Notify student about skill update
    skill_label = dict(DRIVING_SKILLS).get(skill_key, skill_key)
    student_user = User.query.get(student_id)
    if student_user:
        notify_user(student_user, 'skill_updated', **{
            'student_name': student_user.username,
            'skill_name': skill_label,
            'status': status.replace('_', ' ').title(),
            'notes': notes or '',
        })

    return jsonify({'success': True, 'skill_key': skill_key, 'status': status})


@bp.route('/instructor/students')
@login_required
def students():
    """Overview of all students this instructor has taught, with progress."""
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    # Get unique students the instructor has lessons with
    student_ids = db.session.query(Lesson.student_id).filter_by(
        instructor_id=current_user.id
    ).distinct().all()
    student_ids = [sid[0] for sid in student_ids]

    total_skills = len(DRIVING_SKILLS)
    students_data = []

    for sid in student_ids:
        student = User.query.get(sid)
        if not student:
            continue

        # Lesson stats
        lessons = Lesson.query.filter_by(
            instructor_id=current_user.id, student_id=sid
        ).all()
        completed = [ls for ls in lessons if ls.status == 'completed']
        total_hours = round(
            sum((ls.duration or 0) for ls in completed) / 60, 1
        )

        # Feedback stats
        feedbacks = LessonFeedback.query.filter_by(
            instructor_id=current_user.id, student_id=sid
        ).all()
        avg_rating = round(
            sum(f.rating for f in feedbacks) / len(feedbacks), 1
        ) if feedbacks else 0

        # Skill progress
        records = SkillProgress.query.filter_by(student_id=sid).all()
        mastered = sum(1 for r in records if r.status == 'mastered')
        competent = sum(1 for r in records if r.status == 'competent')
        in_prog = sum(1 for r in records if r.status == 'in_progress')
        skill_pct = round(
            (mastered + competent) / total_skills * 100
        ) if total_skills else 0

        # Last lesson date
        last_lesson = max(
            (ls.date for ls in lessons if ls.date), default=None
        )

        students_data.append({
            'student': student,
            'total_lessons': len(completed),
            'total_hours': total_hours,
            'avg_rating': avg_rating,
            'mastered': mastered,
            'competent': competent,
            'in_progress': in_prog,
            'skill_pct': skill_pct,
            'total_skills': total_skills,
            'last_lesson': last_lesson,
        })

    # Sort by most recent lesson
    students_data.sort(
        key=lambda x: x['last_lesson'] or datetime.min.date(),
        reverse=True
    )

    return render_template(
        'instructor/students.html',
        students_data=students_data,
        total_skills=total_skills
    )


@bp.route('/instructor/student/<int:student_id>/progress')
@login_required
def student_progress(student_id):
    """Detailed progress view for a specific student."""
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    student = User.query.get_or_404(student_id)
    if not student.is_student():
        flash('Invalid student.', 'danger')
        return redirect(url_for('instructor.students'))

    # Verify instructor teaches this student
    has_lessons = Lesson.query.filter_by(
        instructor_id=current_user.id, student_id=student_id
    ).first()
    if not has_lessons:
        flash('You have no lessons with this student.', 'danger')
        return redirect(url_for('instructor.students'))

    # Completed lessons
    completed_lessons = Lesson.query.filter_by(
        instructor_id=current_user.id,
        student_id=student_id,
        status='completed'
    ).order_by(Lesson.date.desc()).all()

    total_hours = round(
        sum((ls.duration or 0) for ls in completed_lessons) / 60, 1
    )

    # Feedback history
    feedbacks = LessonFeedback.query.filter_by(
        instructor_id=current_user.id, student_id=student_id
    ).order_by(LessonFeedback.created_at.desc()).all()

    avg_rating = round(
        sum(f.rating for f in feedbacks) / len(feedbacks), 1
    ) if feedbacks else 0

    # Skill progress
    total_skills = len(DRIVING_SKILLS)
    progress_map = {}
    records = SkillProgress.query.filter_by(student_id=student_id).all()
    for r in records:
        progress_map[r.skill_key] = r

    skills = []
    for key, label in DRIVING_SKILLS:
        prog = progress_map.get(key)
        skills.append({
            'key': key,
            'label': label,
            'status': prog.status if prog else 'not_started',
            'notes': prog.notes if prog else '',
        })

    mastered = sum(1 for s in skills if s['status'] == 'mastered')
    competent = sum(1 for s in skills if s['status'] == 'competent')
    in_progress = sum(1 for s in skills if s['status'] == 'in_progress')

    return render_template(
        'instructor/student_progress.html',
        student=student,
        completed_lessons=completed_lessons,
        total_hours=total_hours,
        feedbacks=feedbacks,
        avg_rating=avg_rating,
        skills=skills,
        mastered=mastered,
        competent=competent,
        in_progress=in_progress,
        total_skills=total_skills,
    )


@bp.route('/instructor/student/<int:student_id>/mark-passed', methods=['POST'])
@login_required
def mark_test_passed(student_id):
    """Mark a student as having passed their driving test."""
    if not current_user.is_instructor():
        flash('Access denied.', 'danger')
        return redirect(url_for('main.index'))

    student = User.query.get_or_404(student_id)
    if not student.is_student():
        flash('Invalid student.', 'danger')
        return redirect(url_for('instructor.students'))

    # Verify instructor teaches this student
    has_lessons = Lesson.query.filter_by(
        instructor_id=current_user.id, student_id=student_id
    ).first()
    if not has_lessons:
        flash('You have no lessons with this student.', 'danger')
        return redirect(url_for('instructor.students'))

    if not student.student_profile:
        profile = StudentProfile(user_id=student_id)
        db.session.add(profile)
        db.session.flush()

    from datetime import date
    student.student_profile.test_passed = True
    student.student_profile.test_passed_date = date.today()
    db.session.commit()

    flash(
        f'{student.username} has been marked as passed! 🎉',
        'success'
    )
    return redirect(
        url_for('instructor.student_progress', student_id=student_id)
    )


@bp.route('/instructor/payouts')
@login_required
def payouts():
    """View payout history and earnings summary."""
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    # Earnings from completed lessons (completed payments linked to this instructor)
    completed_payments = (
        db.session.query(Payment)
        .join(Lesson, Payment.lesson_id == Lesson.id)
        .filter(
            Lesson.instructor_id == current_user.id,
            Payment.status == 'completed'
        )
        .all()
    )
    total_earned = sum(p.amount for p in completed_payments)

    # Total already paid out
    all_payouts = InstructorPayout.query.filter_by(
        instructor_id=current_user.id
    ).order_by(InstructorPayout.created_at.desc()).all()

    total_paid_out = sum(
        p.amount for p in all_payouts if p.status in ('completed', 'processing')
    )
    pending_payouts = [p for p in all_payouts if p.status == 'pending']
    pending_amount = sum(p.amount for p in pending_payouts)

    available_balance = total_earned - total_paid_out - pending_amount

    return render_template(
        'instructor/payouts.html',
        payouts=all_payouts,
        total_earned=total_earned,
        total_paid_out=total_paid_out,
        pending_amount=pending_amount,
        available_balance=available_balance,
    )


@bp.route('/instructor/payouts/request', methods=['POST'])
@login_required
def request_payout():
    """Request a payout for available earnings."""
    if not current_user.is_instructor():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    # Calculate available balance
    completed_payments = (
        db.session.query(Payment)
        .join(Lesson, Payment.lesson_id == Lesson.id)
        .filter(
            Lesson.instructor_id == current_user.id,
            Payment.status == 'completed'
        )
        .all()
    )
    total_earned = sum(p.amount for p in completed_payments)

    existing_payouts = InstructorPayout.query.filter_by(
        instructor_id=current_user.id
    ).filter(InstructorPayout.status.in_(['completed', 'processing', 'pending'])).all()
    total_claimed = sum(p.amount for p in existing_payouts)

    available = total_earned - total_claimed
    if available < 1:
        flash('No available balance to withdraw.', 'warning')
        return redirect(url_for('instructor.payouts'))

    # Count completed lessons not yet included in a payout
    lessons_count = (
        db.session.query(func.count(Lesson.id))
        .join(Payment, Payment.lesson_id == Lesson.id)
        .filter(
            Lesson.instructor_id == current_user.id,
            Payment.status == 'completed'
        )
        .scalar() or 0
    )

    payout = InstructorPayout(
        instructor_id=current_user.id,
        amount=round(available, 2),
        lessons_count=lessons_count,
        period_end=date.today(),
        stripe_connect_account_id=(
            current_user.instructor_profile.stripe_connect_account_id
            if current_user.instructor_profile else None
        ),
    )
    db.session.add(payout)
    db.session.commit()

    # Notify instructor
    notify_user(current_user, 'payout_processed', **{
        'instructor_name': current_user.username,
        'amount': f'{available:.2f}',
        'status': 'requested',
        'period_start': 'Start',
        'period_end': date.today().strftime('%b %d, %Y'),
        'lessons_count': lessons_count,
        'notes': '',
    })

    flash(f'Payout of £{available:.2f} requested! Admin will process it shortly.', 'success')
    return redirect(url_for('instructor.payouts'))
