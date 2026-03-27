"""Chatbot action handlers — execute real operations on behalf of the user."""

from datetime import datetime, date, timedelta
from flask import url_for
from flask_login import current_user
from app import db
from app.models import (
    User, Lesson, InstructorProfile, Payment, LessonReschedule, Refund,
    StudentProfile,
)
from app.utils import haversine_distance
from app.notifications import notify_user
import logging

logger = logging.getLogger(__name__)


def find_nearby_instructors(lat=None, lng=None, location_text=None, radius=30):
    """Find instructors near coordinates or by text location."""
    instructors = User.query.filter_by(role='instructor').all()
    results = []

    for inst in instructors:
        p = inst.instructor_profile
        if not p:
            continue

        entry = {
            'id': inst.id,
            'name': inst.username,
            'bio': (p.bio or '')[:120],
            'hourly_rate': p.hourly_rate,
            'address': p.address or 'Not specified',
            'service_radius_km': p.service_radius_km or 15,
            'distance_km': None,
        }

        if lat and lng and p.latitude and p.longitude:
            dist = haversine_distance(lat, lng, p.latitude, p.longitude)
            service_r = p.service_radius_km or 15
            if dist <= max(radius, service_r):
                entry['distance_km'] = round(dist, 1)
                results.append(entry)
        elif location_text and p.address:
            if location_text.lower() in (p.address or '').lower():
                results.append(entry)
        else:
            results.append(entry)

    results.sort(key=lambda x: (x['distance_km'] is None, x['distance_km'] or 9999))
    return results[:10]


def get_upcoming_lessons(user_id, role='student'):
    """Get upcoming confirmed lessons for a student or instructor."""
    if role == 'instructor':
        lessons = Lesson.query.filter(
            Lesson.instructor_id == user_id,
            Lesson.date >= date.today(),
            Lesson.status == 'confirmed'
        ).order_by(Lesson.date, Lesson.time).all()
    else:
        lessons = Lesson.query.filter(
            Lesson.student_id == user_id,
            Lesson.date >= date.today(),
            Lesson.status == 'confirmed'
        ).order_by(Lesson.date, Lesson.time).all()

    results = []
    for l in lessons:
        entry = {
            'id': l.id,
            'date': l.date.strftime('%a %b %d, %Y') if l.date else 'N/A',
            'time': l.time.strftime('%I:%M %p') if l.time else 'N/A',
            'duration_hours': round((l.duration or 60) / 60, 1),
            'pickup_address': l.pickup_address or '',
            'status': l.status,
        }
        if role == 'instructor':
            student = User.query.get(l.student_id)
            entry['student_name'] = student.username if student else 'Unknown'
        else:
            instructor = User.query.get(l.instructor_id)
            entry['instructor_name'] = instructor.username if instructor else 'Unknown'
        results.append(entry)
    return results


def book_lesson(user_id, instructor_id, lesson_date, lesson_time, duration_hours=1, pickup_address=None):
    """Book a lesson for a student."""
    instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
    if not instructor:
        return {'success': False, 'message': 'Instructor not found.'}

    student = User.query.get(user_id)
    if not student or not student.is_student():
        return {'success': False, 'message': 'You must be a student to book lessons.'}

    dur_minutes = int(duration_hours * 60)
    new_start = datetime.combine(lesson_date, lesson_time)
    new_end = new_start + timedelta(minutes=dur_minutes)

    if new_start <= datetime.now():
        return {'success': False, 'message': 'Please choose a future date and time.'}

    # Check conflicts
    conflicts = Lesson.query.filter(
        Lesson.instructor_id == instructor_id,
        Lesson.date == lesson_date,
        Lesson.status == 'confirmed'
    ).all()

    for c in conflicts:
        if c.time:
            ex_start = datetime.combine(c.date, c.time)
            ex_end = ex_start + timedelta(minutes=c.duration or 60)
            if new_start < ex_end and new_end > ex_start:
                return {'success': False, 'message': f'Time slot conflicts with an existing booking. {instructor.username} is busy from {c.time.strftime("%I:%M %p")}.'}

    lesson = Lesson(
        student_id=user_id,
        instructor_id=instructor_id,
        date=lesson_date,
        time=lesson_time,
        duration=dur_minutes,
        status='confirmed',
        pickup_address=pickup_address,
    )
    db.session.add(lesson)
    db.session.commit()

    # Notifications
    notify_ctx = {
        'student_name': student.username,
        'instructor_name': instructor.username,
        'date': lesson_date.strftime('%b %d, %Y'),
        'time': lesson_time.strftime('%I:%M %p'),
        'duration': duration_hours,
        'pickup_address': pickup_address or '',
        'recipient_name': student.username,
    }
    try:
        notify_user(student, 'lesson_booked', **notify_ctx)
        notify_ctx['recipient_name'] = instructor.username
        notify_user(instructor, 'lesson_booked', **notify_ctx)
    except Exception:
        pass

    return {
        'success': True,
        'message': f'Lesson booked with {instructor.username} on {lesson_date.strftime("%b %d, %Y")} at {lesson_time.strftime("%I:%M %p")} ({duration_hours}h).',
        'lesson_id': lesson.id,
    }


def reschedule_lesson(user_id, lesson_id, new_date, new_time, reason=None):
    """Reschedule an existing lesson."""
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return {'success': False, 'message': 'Lesson not found.'}
    if lesson.student_id != user_id:
        return {'success': False, 'message': 'You can only reschedule your own lessons.'}
    if lesson.status != 'confirmed':
        return {'success': False, 'message': 'Only confirmed lessons can be rescheduled.'}
    if lesson.date and lesson.date < date.today():
        return {'success': False, 'message': 'Past lessons cannot be rescheduled.'}

    new_start = datetime.combine(new_date, new_time)
    if new_start <= datetime.now():
        return {'success': False, 'message': 'New date/time must be in the future.'}

    dur_minutes = lesson.duration or 60
    new_end = new_start + timedelta(minutes=dur_minutes)

    conflicts = Lesson.query.filter(
        Lesson.instructor_id == lesson.instructor_id,
        Lesson.date == new_date,
        Lesson.status == 'confirmed',
        Lesson.id != lesson.id
    ).all()

    for c in conflicts:
        if c.time:
            ex_start = datetime.combine(c.date, c.time)
            ex_end = ex_start + timedelta(minutes=c.duration or 60)
            if new_start < ex_end and new_end > ex_start:
                return {'success': False, 'message': 'New time conflicts with another booking.'}

    old_date_str = lesson.date.strftime('%b %d, %Y') if lesson.date else 'N/A'
    old_time_str = lesson.time.strftime('%I:%M %p') if lesson.time else 'N/A'

    reschedule_rec = LessonReschedule(
        lesson_id=lesson.id,
        requested_by_id=user_id,
        old_date=lesson.date,
        old_time=lesson.time,
        new_date=new_date,
        new_time=new_time,
        reason=reason,
    )
    db.session.add(reschedule_rec)

    lesson.date = new_date
    lesson.time = new_time
    db.session.commit()

    instructor = User.query.get(lesson.instructor_id)
    if instructor:
        try:
            notify_user(instructor, 'lesson_rescheduled', **{
                'recipient_name': instructor.username,
                'rescheduled_by': User.query.get(user_id).username,
                'old_date': old_date_str,
                'old_time': old_time_str,
                'new_date': new_date.strftime('%b %d, %Y'),
                'new_time': new_time.strftime('%I:%M %p'),
                'reason': reason or '',
            })
        except Exception:
            pass

    return {
        'success': True,
        'message': f'Lesson rescheduled from {old_date_str} {old_time_str} to {new_date.strftime("%b %d, %Y")} {new_time.strftime("%I:%M %p")}.',
    }


def request_refund(user_id, payment_id=None, lesson_id=None, reason='Requested via AI assistant'):
    """Request a refund for a payment."""
    if payment_id:
        payment = Payment.query.get(payment_id)
    elif lesson_id:
        payment = Payment.query.filter_by(lesson_id=lesson_id, student_id=user_id).first()
    else:
        return {'success': False, 'message': 'Please specify which payment or lesson to refund.'}

    if not payment:
        return {'success': False, 'message': 'Payment not found.'}
    if payment.student_id != user_id:
        return {'success': False, 'message': 'You can only refund your own payments.'}
    if payment.status != 'completed':
        return {'success': False, 'message': 'Only completed payments can be refunded.'}

    existing = Refund.query.filter_by(payment_id=payment.id).filter(
        Refund.status.in_(['pending', 'approved', 'processed'])
    ).first()
    if existing:
        return {'success': False, 'message': 'A refund request already exists for this payment.'}

    refund = Refund(
        payment_id=payment.id,
        lesson_id=payment.lesson_id,
        student_id=user_id,
        amount=payment.amount,
        reason=reason,
        status='pending',
    )
    db.session.add(refund)
    db.session.commit()

    student = User.query.get(user_id)
    try:
        notify_user(student, 'refund_requested', **{
            'recipient_name': student.username,
            'student_name': student.username,
            'amount': f'{payment.amount:.2f}',
            'reason': reason,
        })
    except Exception:
        pass

    return {
        'success': True,
        'message': f'Refund request of £{payment.amount:.2f} submitted. Our team will review it shortly.',
    }


def get_refundable_payments(user_id):
    """Get payments eligible for refund."""
    payments = Payment.query.filter_by(
        student_id=user_id,
        status='completed'
    ).order_by(Payment.created_at.desc()).all()

    results = []
    for p in payments:
        existing = Refund.query.filter_by(payment_id=p.id).filter(
            Refund.status.in_(['pending', 'approved', 'processed'])
        ).first()
        if not existing:
            lesson = Lesson.query.get(p.lesson_id) if p.lesson_id else None
            results.append({
                'payment_id': p.id,
                'amount': p.amount,
                'date': p.created_at.strftime('%b %d, %Y') if p.created_at else 'N/A',
                'lesson_date': lesson.date.strftime('%b %d, %Y') if lesson and lesson.date else 'N/A',
                'description': p.description or 'Lesson payment',
            })
    return results[:10]


def get_available_slots(instructor_id, target_date):
    """Get available time slots for an instructor on a given date."""
    from app.models import InstructorAvailability
    instructor = User.query.get(instructor_id)
    if not instructor:
        return []

    day_of_week = target_date.weekday()
    availability = InstructorAvailability.query.filter_by(
        instructor_id=instructor_id,
        day_of_week=day_of_week
    ).all()

    if not availability:
        return []

    # Get existing bookings for that date
    bookings = Lesson.query.filter(
        Lesson.instructor_id == instructor_id,
        Lesson.date == target_date,
        Lesson.status == 'confirmed'
    ).all()

    booked_times = set()
    for b in bookings:
        if b.time:
            start = datetime.combine(target_date, b.time)
            dur = b.duration or 60
            for m in range(0, dur, 60):
                booked_times.add((start + timedelta(minutes=m)).time())

    slots = []
    for avail in availability:
        current = datetime.combine(target_date, avail.start_time)
        end = datetime.combine(target_date, avail.end_time)
        while current < end:
            t = current.time()
            if t not in booked_times:
                # Skip past times for today
                if target_date == date.today() and current <= datetime.now():
                    current += timedelta(hours=1)
                    continue
                slots.append(t.strftime('%I:%M %p'))
            current += timedelta(hours=1)

    return slots
