from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import (
    User, Lesson, StudentProfile, Payment,
    InstructorAvailability, LessonFeedback, SkillProgress, DRIVING_SKILLS,
    LessonReschedule, Refund, BookingPackage, BLOCK_BOOKING_TIERS,
    InstructorReview
)
from app.forms import BookLessonForm, StudentProfileForm, RescheduleLessonForm, RefundRequestForm, BlockBookingForm, InstructorReviewForm
from app.utils import haversine_distance
from datetime import datetime, date, timedelta
import stripe
import logging
from app.notifications import notify_user

logger = logging.getLogger(__name__)

bp = Blueprint('student', __name__)


@bp.route('/student/dashboard')
@login_required
def dashboard():
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    from datetime import datetime
    # Fetch only upcoming confirmed lessons
    lessons = Lesson.query.filter(
        Lesson.student_id == current_user.id,
        Lesson.date >= datetime.now().date(),
        Lesson.status == 'confirmed'
    ).order_by(Lesson.date).all()
    return render_template('student/dashboard.html', lessons=lessons)


@bp.route('/student/cancel/<int:lesson_id>', methods=['POST'])
@login_required
def cancel_lesson(lesson_id):
    """Cancel an upcoming lesson"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    lesson = Lesson.query.get_or_404(lesson_id)

    # Verify ownership
    if lesson.student_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('student.dashboard'))

    # Only confirmed/upcoming lessons can be cancelled
    if lesson.status != 'confirmed':
        flash('This lesson cannot be cancelled.', 'warning')
        return redirect(url_for('student.dashboard'))

    from datetime import datetime
    if lesson.date and lesson.date < datetime.now().date():
        flash('Past lessons cannot be cancelled.', 'warning')
        return redirect(url_for('student.dashboard'))

    lesson.status = 'cancelled'
    db.session.commit()

    # Notify instructor about cancellation
    instructor = User.query.get(lesson.instructor_id)
    if instructor:
        notify_user(instructor, 'lesson_cancelled', **{
            'recipient_name': instructor.username,
            'cancelled_by': current_user.username,
            'date': lesson.date.strftime('%b %d, %Y') if lesson.date else 'N/A',
            'time': lesson.time.strftime('%I:%M %p') if lesson.time else 'N/A',
        })

    flash('Lesson cancelled successfully.', 'success')
    return redirect(url_for('student.dashboard'))


@bp.route('/student/book', methods=['GET', 'POST'])
@login_required
def book_lesson():
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))
    form = BookLessonForm()
    instructors = User.query.filter_by(role='instructor').all()
    if form.validate_on_submit():
        instructor = User.query.filter_by(id=form.instructor_id.data, role='instructor').first()
        if not instructor:
            flash('Invalid instructor selected.')
            return redirect(url_for('student.book_lesson'))

        # Check for scheduling conflicts
        dur_minutes = form.duration.data * 60
        new_start = datetime.combine(form.date.data, form.time.data)
        new_end = new_start + timedelta(minutes=dur_minutes)

        conflicts = Lesson.query.filter(
            Lesson.instructor_id == instructor.id,
            Lesson.date == form.date.data,
            Lesson.status == 'confirmed'
        ).all()
        has_conflict = False
        for c in conflicts:
            if c.time:
                ex_start = datetime.combine(c.date, c.time)
                ex_end = ex_start + timedelta(minutes=c.duration or 60)
                if new_start < ex_end and new_end > ex_start:
                    has_conflict = True
                    break
        if has_conflict:
            flash('This time slot conflicts with an existing booking. Please choose another time.', 'danger')
            return redirect(url_for('student.book_lesson'))

        lesson = Lesson(
            student_id=current_user.id,
            instructor_id=form.instructor_id.data,
            date=form.date.data,
            time=form.time.data,
            duration=dur_minutes,
            status='confirmed',
            pickup_address=form.pickup_address.data,
            pickup_lat=float(form.pickup_lat.data) if form.pickup_lat.data else None,
            pickup_lng=float(form.pickup_lng.data) if form.pickup_lng.data else None
        )
        db.session.add(lesson)
        db.session.commit()

        # Notify both student and instructor
        instructor = User.query.get(form.instructor_id.data)
        notify_ctx = {
            'student_name': current_user.username,
            'instructor_name': instructor.username if instructor else 'Instructor',
            'date': form.date.data.strftime('%b %d, %Y'),
            'time': form.time.data.strftime('%I:%M %p'),
            'duration': form.duration.data,
            'pickup_address': form.pickup_address.data or '',
            'recipient_name': current_user.username,
        }
        notify_user(current_user, 'lesson_booked', **notify_ctx)
        if instructor:
            notify_ctx['recipient_name'] = instructor.username
            notify_user(instructor, 'lesson_booked', **notify_ctx)

        flash('Lesson booked successfully!')
        return redirect(url_for('student.dashboard'))
    return render_template('student/book_lesson.html', form=form, instructors=instructors)


@bp.route('/api/nearby-instructors')
@login_required
def nearby_instructors():
    """Return instructors near a given lat/lng, sorted by distance."""
    try:
        lat = float(request.args.get('lat', 0))
        lng = float(request.args.get('lng', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid coordinates'}), 400
    radius = float(request.args.get('radius', 30))

    instructors = User.query.filter_by(role='instructor').all()
    results = []
    for inst in instructors:
        p = inst.instructor_profile
        if not p:
            continue
        if p.latitude and p.longitude:
            dist = haversine_distance(lat, lng, p.latitude, p.longitude)
            service_r = p.service_radius_km or 15
            if dist <= max(radius, service_r):
                results.append({
                    'id': inst.id,
                    'username': inst.username,
                    'bio': (p.bio or '')[:100],
                    'hourly_rate': p.hourly_rate,
                    'address': p.address,
                    'distance_km': round(dist, 1),
                    'service_radius_km': service_r
                })
        else:
            # Instructors without location still appear, but without distance
            results.append({
                'id': inst.id,
                'username': inst.username,
                'bio': (p.bio or '')[:100],
                'hourly_rate': p.hourly_rate,
                'address': p.address,
                'distance_km': None,
                'service_radius_km': p.service_radius_km or 15
            })

    # Sort: nearby first, no-location last
    results.sort(key=lambda x: (x['distance_km'] is None, x['distance_km'] or 9999))
    return jsonify({'instructors': results})


@bp.route('/api/instructor-slots/<int:instructor_id>')
@login_required
def instructor_slots(instructor_id):
    """Return FullCalendar-compatible events for an instructor's available and booked slots."""
    start_str = request.args.get('start', '')
    end_str = request.args.get('end', '')
    try:
        range_start = datetime.fromisoformat(start_str[:10]).date() if start_str else date.today()
        range_end = datetime.fromisoformat(end_str[:10]).date() if end_str else range_start + timedelta(days=42)
    except (ValueError, TypeError):
        range_start = date.today()
        range_end = range_start + timedelta(days=42)

    # Get instructor's weekly availability
    avail_slots = InstructorAvailability.query.filter_by(instructor_id=instructor_id).all()
    avail_by_day = {}
    for s in avail_slots:
        avail_by_day.setdefault(s.day_of_week, []).append((s.start_time, s.end_time))

    # Get existing lessons in range
    booked = Lesson.query.filter(
        Lesson.instructor_id == instructor_id,
        Lesson.date >= range_start,
        Lesson.date <= range_end,
        Lesson.status == 'confirmed'
    ).all()

    booked_set = set()
    for b in booked:
        if b.time and b.date:
            bstart = datetime.combine(b.date, b.time)
            dur = b.duration or 60
            # Mark each 30-min block as booked
            for i in range(0, dur, 30):
                booked_set.add(bstart + timedelta(minutes=i))

    events = []
    current = range_start
    now = datetime.now()

    while current <= range_end:
        dow = current.weekday()  # 0=Monday
        if dow in avail_by_day:
            for start_t, end_t in avail_by_day[dow]:
                # Generate 1-hour slots
                slot_start = datetime.combine(current, start_t)
                slot_end_limit = datetime.combine(current, end_t)
                while slot_start + timedelta(hours=1) <= slot_end_limit:
                    slot_end = slot_start + timedelta(hours=1)
                    # Check if past
                    if slot_start <= now:
                        slot_start = slot_end
                        continue
                    # Check if booked
                    is_booked = False
                    for i in range(0, 60, 30):
                        if (slot_start + timedelta(minutes=i)) in booked_set:
                            is_booked = True
                            break
                    events.append({
                        'title': 'Booked' if is_booked else 'Available',
                        'start': slot_start.isoformat(),
                        'end': slot_end.isoformat(),
                        'color': '#94a3b8' if is_booked else '#10b981',
                        'textColor': '#fff',
                        'extendedProps': {
                            'available': not is_booked
                        }
                    })
                    slot_start = slot_end
        current += timedelta(days=1)

    return jsonify(events)


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


# ===== Payment Routes =====

@bp.route('/student/payments')
@login_required
def payments():
    """View payment history"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    student_payments = Payment.query.filter_by(
        student_id=current_user.id
    ).order_by(Payment.created_at.desc()).all()

    return render_template('student/payments.html', payments=student_payments)


@bp.route('/student/pay/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
def pay_lesson(lesson_id):
    """Pay for a specific lesson"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    lesson = Lesson.query.get_or_404(lesson_id)

    # Verify ownership
    if lesson.student_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('student.dashboard'))

    # Check if already paid
    existing_payment = Payment.query.filter_by(
        lesson_id=lesson_id, status='completed'
    ).first()
    if existing_payment:
        flash('This lesson has already been paid for.')
        return redirect(url_for('student.dashboard'))

    lesson_price = current_app.config.get('LESSON_PRICE_GBP', 35.00)
    # Adjust price by duration (base price is per hour)
    hours = (lesson.duration or 60) / 60
    total_price = round(lesson_price * hours, 2)

    stripe_key = current_app.config.get('STRIPE_PUBLIC_KEY', '')

    return render_template(
        'student/pay_lesson.html',
        lesson=lesson,
        total_price=total_price,
        stripe_public_key=stripe_key
    )


@bp.route('/student/create-payment-intent/<int:lesson_id>', methods=['POST'])
@login_required
def create_payment_intent(lesson_id):
    """Create a Stripe PaymentIntent for a lesson"""
    if not current_user.is_student():
        return jsonify({'error': 'Access denied'}), 403

    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.student_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    # Check if already paid
    existing_payment = Payment.query.filter_by(
        lesson_id=lesson_id, status='completed'
    ).first()
    if existing_payment:
        return jsonify({'error': 'Lesson already paid'}), 400

    try:
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        lesson_price = current_app.config.get('LESSON_PRICE_GBP', 35.00)
        hours = (lesson.duration or 60) / 60
        total_price = round(lesson_price * hours, 2)
        amount_pence = int(total_price * 100)

        intent = stripe.PaymentIntent.create(
            amount=amount_pence,
            currency='gbp',
            metadata={
                'student_id': str(current_user.id),
                'lesson_id': str(lesson_id),
                'student_email': current_user.email
            },
            description=(
                f'Driving lesson - {lesson.date} with '
                f'{lesson.instructor.username if lesson.instructor else "instructor"}'
            )
        )

        # Create pending payment record
        payment = Payment(
            student_id=current_user.id,
            lesson_id=lesson_id,
            amount=total_price,
            currency='GBP',
            status='pending',
            stripe_payment_intent_id=intent.id,
            description=f'Lesson on {lesson.date}'
        )
        db.session.add(payment)
        db.session.commit()

        return jsonify({
            'clientSecret': intent.client_secret
        })
    except stripe.error.StripeError as e:
        logger.error(f'Stripe error: {str(e)}')
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Payment error: {str(e)}')
        return jsonify({'error': 'Payment processing failed'}), 500


@bp.route('/student/payment-success/<int:lesson_id>')
@login_required
def payment_success(lesson_id):
    """Handle successful payment"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    # Update payment status
    payment = Payment.query.filter_by(
        lesson_id=lesson_id,
        student_id=current_user.id,
        status='pending'
    ).first()

    if payment:
        payment.status = 'completed'
        db.session.commit()

        # Notify student about successful payment
        lesson = Lesson.query.get(lesson_id)
        notify_user(current_user, 'payment_success', **{
            'student_name': current_user.username,
            'amount': f'{payment.amount:.2f}',
            'date': lesson.date.strftime('%b %d, %Y') if lesson and lesson.date else 'N/A',
        })

    flash('Payment successful! Your lesson is confirmed.', 'success')
    return redirect(url_for('student.dashboard'))


@bp.route('/student/progress')
@login_required
def progress():
    """View student's progress: completed lessons, feedback, and skills."""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    # Completed lessons with feedback
    completed_lessons = Lesson.query.filter_by(
        student_id=current_user.id, status='completed'
    ).order_by(Lesson.date.desc()).all()

    total_lessons = Lesson.query.filter_by(
        student_id=current_user.id
    ).count()

    total_hours = sum(
        (les.duration or 0) / 60 for les in completed_lessons
    )

    # Feedback history
    feedback_list = LessonFeedback.query.filter_by(
        student_id=current_user.id
    ).order_by(LessonFeedback.created_at.desc()).all()

    avg_rating = 0.0
    if feedback_list:
        avg_rating = sum(f.rating for f in feedback_list) / len(
            feedback_list
        )

    # Skill checklist
    progress_map = {}
    records = SkillProgress.query.filter_by(
        student_id=current_user.id
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

    # Skill completion stats
    total_skills = len(DRIVING_SKILLS)
    mastered = sum(1 for s in skills if s['status'] == 'mastered')
    competent = sum(1 for s in skills if s['status'] == 'competent')
    in_prog = sum(1 for s in skills if s['status'] == 'in_progress')

    return render_template(
        'student/progress.html',
        completed_lessons=completed_lessons,
        total_lessons=total_lessons,
        total_hours=round(total_hours, 1),
        feedback_list=feedback_list,
        avg_rating=round(avg_rating, 1),
        skills=skills,
        total_skills=total_skills,
        mastered=mastered,
        competent=competent,
        in_progress=in_prog
    )


# ===== Lesson Rescheduling Routes =====

@bp.route('/student/reschedule/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
def reschedule_lesson(lesson_id):
    """Reschedule an upcoming confirmed lesson"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    lesson = Lesson.query.get_or_404(lesson_id)

    if lesson.student_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('student.dashboard'))

    if lesson.status != 'confirmed':
        flash('Only confirmed lessons can be rescheduled.', 'warning')
        return redirect(url_for('student.dashboard'))

    if lesson.date and lesson.date < datetime.now().date():
        flash('Past lessons cannot be rescheduled.', 'warning')
        return redirect(url_for('student.dashboard'))

    form = RescheduleLessonForm()

    if form.validate_on_submit():
        new_date = form.new_date.data
        new_time = form.new_time.data

        # Must be in the future
        if new_date < date.today() or (new_date == date.today() and datetime.combine(new_date, new_time) <= datetime.now()):
            flash('Please select a future date and time.', 'danger')
            return render_template('student/reschedule_lesson.html', form=form, lesson=lesson)

        # Check for scheduling conflicts with the instructor
        dur_minutes = lesson.duration or 60
        new_start = datetime.combine(new_date, new_time)
        new_end = new_start + timedelta(minutes=dur_minutes)

        conflicts = Lesson.query.filter(
            Lesson.instructor_id == lesson.instructor_id,
            Lesson.date == new_date,
            Lesson.status == 'confirmed',
            Lesson.id != lesson.id
        ).all()

        has_conflict = False
        for c in conflicts:
            if c.time:
                ex_start = datetime.combine(c.date, c.time)
                ex_end = ex_start + timedelta(minutes=c.duration or 60)
                if new_start < ex_end and new_end > ex_start:
                    has_conflict = True
                    break

        if has_conflict:
            flash('This time slot conflicts with an existing booking. Please choose another time.', 'danger')
            return render_template('student/reschedule_lesson.html', form=form, lesson=lesson)

        # Record the reschedule
        reschedule = LessonReschedule(
            lesson_id=lesson.id,
            requested_by_id=current_user.id,
            old_date=lesson.date,
            old_time=lesson.time,
            new_date=new_date,
            new_time=new_time,
            reason=form.reason.data
        )
        db.session.add(reschedule)

        old_date_str = lesson.date.strftime('%b %d, %Y') if lesson.date else 'N/A'
        old_time_str = lesson.time.strftime('%I:%M %p') if lesson.time else 'N/A'

        lesson.date = new_date
        lesson.time = new_time
        db.session.commit()

        # Notify instructor
        instructor = User.query.get(lesson.instructor_id)
        if instructor:
            notify_user(instructor, 'lesson_rescheduled', **{
                'recipient_name': instructor.username,
                'rescheduled_by': current_user.username,
                'old_date': old_date_str,
                'old_time': old_time_str,
                'new_date': new_date.strftime('%b %d, %Y'),
                'new_time': new_time.strftime('%I:%M %p'),
                'reason': form.reason.data or '',
            })

        flash('Lesson rescheduled successfully!', 'success')
        return redirect(url_for('student.dashboard'))

    return render_template('student/reschedule_lesson.html', form=form, lesson=lesson)


# ===== Refund Routes =====

@bp.route('/student/refund/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def request_refund(payment_id):
    """Request a refund for a completed payment"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    payment = Payment.query.get_or_404(payment_id)

    if payment.student_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('student.payments'))

    if payment.status != 'completed':
        flash('Only completed payments can be refunded.', 'warning')
        return redirect(url_for('student.payments'))

    # Check if a refund already exists for this payment
    existing_refund = Refund.query.filter_by(
        payment_id=payment_id
    ).filter(Refund.status.in_(['pending', 'approved', 'processed'])).first()
    if existing_refund:
        flash('A refund request already exists for this payment.', 'info')
        return redirect(url_for('student.payments'))

    form = RefundRequestForm()

    if form.validate_on_submit():
        refund = Refund(
            payment_id=payment.id,
            lesson_id=payment.lesson_id,
            student_id=current_user.id,
            amount=payment.amount,
            reason=form.reason.data,
            status='pending'
        )
        db.session.add(refund)
        db.session.commit()

        # Notify student
        notify_user(current_user, 'refund_requested', **{
            'recipient_name': current_user.username,
            'student_name': current_user.username,
            'amount': f'{payment.amount:.2f}',
            'reason': form.reason.data,
        })

        flash('Refund request submitted. Our team will review it shortly.', 'success')
        return redirect(url_for('student.payments'))

    return render_template('student/request_refund.html', form=form, payment=payment)


# ===== Block Booking Routes =====

@bp.route('/student/packages')
@login_required
def packages():
    """View active and past block booking packages"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    active_packages = BookingPackage.query.filter_by(
        student_id=current_user.id, status='active'
    ).all()
    past_packages = BookingPackage.query.filter_by(
        student_id=current_user.id
    ).filter(BookingPackage.status != 'active').all()

    return render_template(
        'student/packages.html',
        active_packages=active_packages,
        past_packages=past_packages,
        tiers=BLOCK_BOOKING_TIERS
    )


@bp.route('/student/review/<int:instructor_id>', methods=['GET', 'POST'])
@login_required
def write_review(instructor_id):
    """Submit a public review for an instructor."""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    instructor = User.query.get_or_404(instructor_id)
    if not instructor.is_instructor():
        flash('Invalid instructor.', 'danger')
        return redirect(url_for('student.dashboard'))

    # Verify student has at least one completed lesson with this instructor
    completed_lesson = Lesson.query.filter_by(
        student_id=current_user.id,
        instructor_id=instructor_id,
        status='completed'
    ).first()
    if not completed_lesson:
        flash('You can only review instructors you have completed lessons with.', 'warning')
        return redirect(url_for('student.dashboard'))

    # Check if already reviewed
    existing = InstructorReview.query.filter_by(
        instructor_id=instructor_id,
        student_id=current_user.id
    ).first()
    if existing:
        flash('You have already reviewed this instructor.', 'info')
        return redirect(url_for('main.instructor_reviews', instructor_id=instructor_id))

    form = InstructorReviewForm()
    if form.validate_on_submit():
        review = InstructorReview(
            instructor_id=instructor_id,
            student_id=current_user.id,
            rating=int(form.rating.data),
            title=form.title.data,
            comment=form.comment.data,
        )
        db.session.add(review)
        db.session.commit()

        # Notify the instructor
        notify_user(instructor, 'review_received', **{
            'instructor_name': instructor.username,
            'student_name': current_user.username,
            'rating': int(form.rating.data),
            'title': form.title.data,
            'comment': form.comment.data,
        })

        flash('Review submitted successfully! Thank you for your feedback.', 'success')
        return redirect(url_for('main.instructor_reviews', instructor_id=instructor_id))

    return render_template(
        'student/write_review.html', form=form, instructor=instructor
    )


@bp.route('/student/reviews')
@login_required
def my_reviews():
    """Show instructors the student can review and existing reviews."""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    # Get instructors from completed lessons
    completed_instructor_ids = db.session.query(
        Lesson.instructor_id
    ).filter(
        Lesson.student_id == current_user.id,
        Lesson.status == 'completed'
    ).distinct().all()
    instructor_ids = [r[0] for r in completed_instructor_ids]

    # Already-reviewed instructor IDs
    reviewed_ids = {r.instructor_id for r in InstructorReview.query.filter_by(
        student_id=current_user.id
    ).all()}

    reviewable_instructors = User.query.filter(
        User.id.in_(instructor_ids),
        ~User.id.in_(reviewed_ids) if reviewed_ids else True
    ).all() if instructor_ids else []

    my_reviews = InstructorReview.query.filter_by(
        student_id=current_user.id
    ).order_by(InstructorReview.created_at.desc()).all()

    return render_template(
        'student/my_reviews.html',
        reviewable_instructors=reviewable_instructors,
        my_reviews=my_reviews,
    )


@bp.route('/student/book-package', methods=['GET', 'POST'])
@login_required
def book_package():
    """Purchase a block of lessons at a discounted rate"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    form = BlockBookingForm()
    instructors = User.query.filter_by(role='instructor').all()

    if form.validate_on_submit():
        instructor = User.query.filter_by(
            id=form.instructor_id.data, role='instructor'
        ).first()
        if not instructor:
            flash('Invalid instructor selected.', 'danger')
            return redirect(url_for('student.book_package'))

        tier_lessons = int(form.package_tier.data)
        tier = next((t for t in BLOCK_BOOKING_TIERS if t[0] == tier_lessons), None)
        if not tier:
            flash('Invalid package tier.', 'danger')
            return redirect(url_for('student.book_package'))

        total_lessons, discount_percent, _ = tier
        lesson_price = current_app.config.get('LESSON_PRICE_GBP', 35.00)
        price_per_lesson = round(lesson_price * (1 - discount_percent / 100), 2)
        total_price = round(price_per_lesson * total_lessons, 2)

        package = BookingPackage(
            student_id=current_user.id,
            instructor_id=instructor.id,
            total_lessons=total_lessons,
            lessons_used=0,
            price_per_lesson=price_per_lesson,
            discount_percent=discount_percent,
            total_price=total_price,
            status='active',
            payment_status='pending'
        )
        db.session.add(package)
        db.session.commit()

        stripe_key = current_app.config.get('STRIPE_PUBLIC_KEY', '')
        return render_template(
            'student/pay_package.html',
            package=package,
            instructor=instructor,
            stripe_public_key=stripe_key
        )

    return render_template(
        'student/book_package.html',
        form=form,
        instructors=instructors,
        tiers=BLOCK_BOOKING_TIERS,
        lesson_price=current_app.config.get('LESSON_PRICE_GBP', 35.00)
    )


@bp.route('/student/create-package-payment-intent/<int:package_id>', methods=['POST'])
@login_required
def create_package_payment_intent(package_id):
    """Create a Stripe PaymentIntent for a block booking package"""
    if not current_user.is_student():
        return jsonify({'error': 'Access denied'}), 403

    package = BookingPackage.query.get_or_404(package_id)
    if package.student_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    if package.payment_status == 'completed':
        return jsonify({'error': 'Package already paid'}), 400

    try:
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        amount_pence = int(package.total_price * 100)

        intent = stripe.PaymentIntent.create(
            amount=amount_pence,
            currency='gbp',
            metadata={
                'student_id': str(current_user.id),
                'package_id': str(package_id),
                'student_email': current_user.email
            },
            description=f'Block booking – {package.total_lessons} lessons ({package.discount_percent}% off)'
        )

        package.stripe_payment_intent_id = intent.id
        db.session.commit()

        return jsonify({'clientSecret': intent.client_secret})
    except stripe.error.StripeError as e:
        logger.error(f'Stripe error: {str(e)}')
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Package payment error: {str(e)}')
        return jsonify({'error': 'Payment processing failed'}), 500


@bp.route('/student/package-payment-success/<int:package_id>')
@login_required
def package_payment_success(package_id):
    """Handle successful package payment"""
    if not current_user.is_student():
        flash('Access denied.')
        return redirect(url_for('main.index'))

    package = BookingPackage.query.get_or_404(package_id)
    if package.student_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('student.dashboard'))

    if package.payment_status != 'completed':
        package.payment_status = 'completed'
        db.session.commit()

        instructor = User.query.get(package.instructor_id)
        notify_user(current_user, 'package_purchased', **{
            'student_name': current_user.username,
            'total_lessons': package.total_lessons,
            'discount_percent': package.discount_percent,
            'total_price': f'{package.total_price:.2f}',
        })

    flash(f'Package purchased! You have {package.lessons_remaining} lessons available.', 'success')
    return redirect(url_for('student.packages'))
