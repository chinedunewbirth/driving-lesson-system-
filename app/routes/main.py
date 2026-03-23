from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app.models import (
    User, Lesson, InstructorProfile, StudentProfile, NotificationPreference,
    InstructorReview, InAppNotification
)
from app.forms import NotificationPreferenceForm
from sqlalchemy import func
from app import db

bp = Blueprint('main', __name__)


@bp.route('/')
@bp.route('/index')
def index():
    # Query instructor performance stats
    instructors = db.session.query(
        User.id,
        User.username,
        InstructorProfile.bio,
        InstructorProfile.hourly_rate,
        func.count(Lesson.id).label('total_lessons'),
        func.sum(
            db.case(
                (Lesson.status == 'completed', 1),
                else_=0
            )
        ).label('completed_lessons'),
        func.sum(
            db.case(
                (Lesson.status == 'completed', Lesson.duration),
                else_=0
            )
        ).label('total_minutes')
    ).join(
        InstructorProfile, User.id == InstructorProfile.user_id
    ).outerjoin(
        Lesson, User.id == Lesson.instructor_id
    ).filter(
        User.role == 'instructor'
    ).group_by(
        User.id, User.username, InstructorProfile.bio, InstructorProfile.hourly_rate
    ).all()

    # Count students who passed per instructor
    passed_counts = db.session.query(
        Lesson.instructor_id,
        func.count(func.distinct(Lesson.student_id)).label('passed_count')
    ).join(
        StudentProfile, Lesson.student_id == StudentProfile.user_id
    ).filter(
        StudentProfile.test_passed.is_(True)
    ).group_by(
        Lesson.instructor_id
    ).all()
    passed_map = {r.instructor_id: r.passed_count for r in passed_counts}

    # Average review ratings per instructor
    review_stats = db.session.query(
        InstructorReview.instructor_id,
        func.avg(InstructorReview.rating).label('avg_rating'),
        func.count(InstructorReview.id).label('review_count')
    ).group_by(InstructorReview.instructor_id).all()
    review_map = {r.instructor_id: {'avg': round(float(r.avg_rating), 1), 'count': r.review_count} for r in review_stats}

    instructor_data = []
    for inst in instructors:
        completed = inst.completed_lessons or 0
        total = inst.total_lessons or 0
        minutes = inst.total_minutes or 0
        review_info = review_map.get(inst.id, {'avg': 0, 'count': 0})
        instructor_data.append({
            'id': inst.id,
            'username': inst.username,
            'bio': inst.bio or 'Certified driving instructor',
            'hourly_rate': inst.hourly_rate or 0,
            'total_lessons': total,
            'completed_lessons': completed,
            'hours_taught': round(minutes / 60, 1),
            'completion_rate': round(
                (completed / total * 100) if total > 0 else 0
            ),
            'students_passed': passed_map.get(inst.id, 0),
            'avg_rating': review_info['avg'],
            'review_count': review_info['count'],
        })

    return render_template('index.html', title='Home', instructors=instructor_data)


@bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def notification_settings():
    """Manage notification preferences for email and WhatsApp."""
    pref = NotificationPreference.query.filter_by(
        user_id=current_user.id
    ).first()
    if not pref:
        pref = NotificationPreference(user_id=current_user.id)
        db.session.add(pref)
        db.session.commit()

    form = NotificationPreferenceForm()

    if form.validate_on_submit():
        pref.email_enabled = form.email_enabled.data
        pref.whatsapp_enabled = form.whatsapp_enabled.data
        pref.sms_enabled = form.sms_enabled.data
        pref.notify_lesson_booked = form.notify_lesson_booked.data
        pref.notify_lesson_cancelled = form.notify_lesson_cancelled.data
        pref.notify_feedback = form.notify_feedback.data
        pref.notify_payment = form.notify_payment.data
        pref.notify_skill_update = form.notify_skill_update.data

        # Save phone to the user's profile
        phone = form.phone.data
        if phone:
            if current_user.is_student():
                if not current_user.student_profile:
                    from app.models import StudentProfile
                    sp = StudentProfile(user_id=current_user.id)
                    db.session.add(sp)
                    db.session.flush()
                current_user.student_profile.phone = phone
            elif current_user.is_instructor():
                if current_user.instructor_profile:
                    current_user.instructor_profile.phone = phone

        db.session.commit()
        flash('Notification preferences saved!', 'success')
        return redirect(url_for('main.notification_settings'))

    elif request.method == 'GET':
        form.email_enabled.data = pref.email_enabled
        form.whatsapp_enabled.data = pref.whatsapp_enabled
        form.sms_enabled.data = getattr(pref, 'sms_enabled', False)
        form.notify_lesson_booked.data = pref.notify_lesson_booked
        form.notify_lesson_cancelled.data = pref.notify_lesson_cancelled
        form.notify_feedback.data = pref.notify_feedback
        form.notify_payment.data = pref.notify_payment
        form.notify_skill_update.data = pref.notify_skill_update
        # Pre-fill phone
        if current_user.is_student() and current_user.student_profile:
            form.phone.data = current_user.student_profile.phone or ''
        elif (current_user.is_instructor()
              and current_user.instructor_profile):
            form.phone.data = (
                current_user.instructor_profile.phone or ''
            )

    return render_template(
        'notifications.html', form=form, pref=pref
    )


@bp.route('/instructor/<int:instructor_id>/reviews')
def instructor_reviews(instructor_id):
    """Public page showing all reviews for an instructor."""
    instructor = User.query.get_or_404(instructor_id)
    if not instructor.is_instructor():
        flash('Invalid instructor.', 'danger')
        return redirect(url_for('main.index'))

    reviews = InstructorReview.query.filter_by(
        instructor_id=instructor_id
    ).order_by(InstructorReview.created_at.desc()).all()

    avg_rating = 0
    if reviews:
        avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1)

    profile = instructor.instructor_profile

    return render_template(
        'instructor_reviews.html',
        instructor=instructor,
        profile=profile,
        reviews=reviews,
        avg_rating=avg_rating,
    )


@bp.route('/notifications/inbox')
@login_required
def notification_inbox():
    """View all in-app notifications."""
    notifications = InAppNotification.query.filter_by(
        user_id=current_user.id
    ).order_by(InAppNotification.created_at.desc()).limit(50).all()

    # Mark all as read
    unread = InAppNotification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).all()
    for n in unread:
        n.is_read = True
    db.session.commit()

    return render_template('notification_inbox.html', notifications=notifications)


@bp.route('/notifications/unread-count')
@login_required
def unread_count():
    """Return unread notification count as JSON (for navbar badge)."""
    count = InAppNotification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    return jsonify({'count': count})


@bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Mark a single notification as read."""
    notif = InAppNotification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    notif.is_read = True
    db.session.commit()
    if notif.link:
        return redirect(notif.link)
    return redirect(url_for('main.notification_inbox'))
