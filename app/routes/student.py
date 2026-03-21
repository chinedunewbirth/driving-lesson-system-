from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User, Lesson, StudentProfile, Payment
from app.forms import BookLessonForm, StudentProfileForm
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
            description=f'Driving lesson - {lesson.date} with {lesson.instructor.username if lesson.instructor else "instructor"}'
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