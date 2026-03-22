from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User, Lesson, StudentProfile, Payment, InstructorAvailability
from app.forms import BookLessonForm, StudentProfileForm
from app.utils import haversine_distance
from datetime import datetime, date, timedelta
import stripe
import logging

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

    flash('Payment successful! Your lesson is confirmed.', 'success')
    return redirect(url_for('student.dashboard'))
