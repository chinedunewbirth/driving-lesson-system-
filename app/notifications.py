"""
Notification service for email and WhatsApp notifications.
Uses Flask-Mail for email and Twilio for WhatsApp.
"""
import logging
from flask import current_app, render_template_string
from flask_mail import Message

logger = logging.getLogger(__name__)

# ── Email Templates ──────────────────────────────────────────────

EMAIL_TEMPLATES = {
    'welcome': {
        'subject': 'Welcome to DriveSmart! 🚗',
        'body': '''
Hello {{ username }},

Welcome to DriveSmart! Your account has been created successfully.

Role: {{ role }}
Email: {{ email }}

Log in at {{ login_url }} to get started.

Happy driving!
The DriveSmart Team
'''
    },
    'lesson_booked': {
        'subject': 'Lesson Booked – {{ date }}',
        'body': '''
Hello {{ recipient_name }},

A driving lesson has been booked:

Student: {{ student_name }}
Instructor: {{ instructor_name }}
Date: {{ date }}
Time: {{ time }}
Duration: {{ duration }} hour(s)
{% if pickup_address %}Pickup: {{ pickup_address }}{% endif %}

View your dashboard for more details.

The DriveSmart Team
'''
    },
    'lesson_cancelled': {
        'subject': 'Lesson Cancelled – {{ date }}',
        'body': '''
Hello {{ recipient_name }},

A driving lesson has been cancelled:

Cancelled by: {{ cancelled_by }}
Date: {{ date }}
Time: {{ time }}

If this was unexpected, please contact the other party.

The DriveSmart Team
'''
    },
    'feedback_received': {
        'subject': 'New Feedback from {{ instructor_name }}',
        'body': '''
Hello {{ student_name }},

Your instructor {{ instructor_name }} has left feedback for your lesson on {{ date }}:

Rating: {{ rating }}/5
{% if notes %}Notes: {{ notes }}{% endif %}
{% if strengths %}Strengths: {{ strengths }}{% endif %}
{% if areas_to_improve %}To Improve: {{ areas_to_improve }}{% endif %}

Check your progress dashboard for full details.

The DriveSmart Team
'''
    },
    'payment_success': {
        'subject': 'Payment Confirmed – £{{ amount }}',
        'body': '''
Hello {{ student_name }},

Your payment of £{{ amount }} has been processed successfully.

Lesson Date: {{ date }}
Status: Confirmed

Thank you for choosing DriveSmart!

The DriveSmart Team
'''
    },
    'skill_updated': {
        'subject': 'Skill Update: {{ skill_name }}',
        'body': '''
Hello {{ student_name }},

Your instructor has updated your skill progress:

Skill: {{ skill_name }}
New Status: {{ status }}
{% if notes %}Notes: {{ notes }}{% endif %}

Keep up the great work!

The DriveSmart Team
'''
    },
    'lesson_rescheduled': {
        'subject': 'Lesson Rescheduled – {{ new_date }}',
        'body': '''
Hello {{ recipient_name }},

A driving lesson has been rescheduled:

Rescheduled by: {{ rescheduled_by }}
Original: {{ old_date }} at {{ old_time }}
New: {{ new_date }} at {{ new_time }}
{% if reason %}Reason: {{ reason }}{% endif %}

Check your dashboard for the updated schedule.

The DriveSmart Team
'''
    },
    'refund_requested': {
        'subject': 'Refund Requested – £{{ amount }}',
        'body': '''
Hello {{ recipient_name }},

A refund request has been submitted:

Student: {{ student_name }}
Amount: £{{ amount }}
{% if reason %}Reason: {{ reason }}{% endif %}

The admin team will review this shortly.

The DriveSmart Team
'''
    },
    'refund_processed': {
        'subject': 'Refund {{ status|capitalize }} – £{{ amount }}',
        'body': '''
Hello {{ student_name }},

Your refund request for £{{ amount }} has been {{ status }}.

{% if status == "approved" %}The refund will be processed to your original payment method within 5-10 business days.{% endif %}

The DriveSmart Team
'''
    },
    'package_purchased': {
        'subject': 'Block Booking Confirmed – {{ total_lessons }} Lessons',
        'body': '''
Hello {{ student_name }},

Your block booking has been confirmed!

Package: {{ total_lessons }} lessons
Discount: {{ discount_percent }}% off
Total: £{{ total_price }}

You can now book your lessons from your dashboard.

The DriveSmart Team
'''
    },
    'lesson_reminder': {
        'subject': 'Lesson Reminder – {{ date }} at {{ time }}',
        'body': '''
Hello {{ recipient_name }},

This is a friendly reminder that you have a driving lesson coming up:

Instructor: {{ instructor_name }}
Date: {{ date }}
Time: {{ time }}
Duration: {{ duration }} hour(s)
{% if pickup_address %}Pickup: {{ pickup_address }}{% endif %}

Please be ready and on time. Good luck!

The DriveSmart Team
'''
    },
    'review_received': {
        'subject': 'New Review from {{ student_name }} – {{ rating }}/5',
        'body': '''
Hello {{ instructor_name }},

A student has left a review for you:

Student: {{ student_name }}
Rating: {{ rating }}/5
Title: {{ title }}
Comment: {{ comment }}

View all your reviews on the DriveSmart platform.

The DriveSmart Team
'''
    },    'payout_processed': {
        'subject': 'Payout {{ status|capitalize }} \u2013 \u00a3{{ amount }}',
        'body': '''
Hello {{ instructor_name }},

Your payout of \u00a3{{ amount }} has been {{ status }}.

Period: {{ period_start }} to {{ period_end }}
Lessons: {{ lessons_count }}
{% if notes %}Notes: {{ notes }}{% endif %}

View your earnings dashboard for full details.

The DriveSmart Team
'''
    },}

# ── WhatsApp Templates ───────────────────────────────────────────

WHATSAPP_TEMPLATES = {
    'welcome': (
        '🚗 Welcome to DriveSmart, {{ username }}! '
        'Your {{ role }} account is ready. '
        'Log in to get started.'
    ),
    'lesson_booked': (
        '📅 Lesson Booked!\n'
        'Student: {{ student_name }}\n'
        'Instructor: {{ instructor_name }}\n'
        'Date: {{ date }} at {{ time }}\n'
        'Duration: {{ duration }}h'
    ),
    'lesson_cancelled': (
        '❌ Lesson Cancelled\n'
        'Cancelled by: {{ cancelled_by }}\n'
        'Date: {{ date }} at {{ time }}'
    ),
    'feedback_received': (
        '⭐ New Feedback!\n'
        'From: {{ instructor_name }}\n'
        'Rating: {{ rating }}/5\n'
        '{{ notes }}'
    ),
    'payment_success': (
        '✅ Payment Confirmed: £{{ amount }}\n'
        'Lesson: {{ date }}'
    ),
    'skill_updated': (
        '📊 Skill Update: {{ skill_name }}\n'
        'Status: {{ status }}'
    ),
    'lesson_rescheduled': (
        '🔄 Lesson Rescheduled\n'
        'Old: {{ old_date }} at {{ old_time }}\n'
        'New: {{ new_date }} at {{ new_time }}'
    ),
    'refund_requested': (
        '💰 Refund Requested: £{{ amount }}\n'
        'Student: {{ student_name }}'
    ),
    'refund_processed': (
        '💰 Refund {{ status|capitalize }}: £{{ amount }}'
    ),
    'package_purchased': (
        '📦 Block Booking Confirmed!\n'
        '{{ total_lessons }} lessons – {{ discount_percent }}% off\n'
        'Total: £{{ total_price }}'
    ),
    'lesson_reminder': (
        '⏰ Lesson Reminder!\n'
        'Instructor: {{ instructor_name }}\n'
        'Date: {{ date }} at {{ time }}\n'
        'Duration: {{ duration }}h\n'
        'Be ready and on time!'
    ),
    'review_received': (
        '⭐ New Review!\n'
        'From: {{ student_name }}\n'
        'Rating: {{ rating }}/5\n'
        '{{ title }}'
    ),    'payout_processed': (
        '\U0001f4b0 Payout {{ status|capitalize }}: \u00a3{{ amount }}\n'
        'Period: {{ period_start }} to {{ period_end }}'
    ),}


# ── SMS Templates (short text, reuses WhatsApp style) ────────────

SMS_TEMPLATES = {
    'welcome': 'Welcome to DriveSmart, {{ username }}! Your {{ role }} account is ready. Log in to get started.',
    'lesson_booked': 'DriveSmart: Lesson booked! {{ date }} at {{ time }} with {{ instructor_name }}. Duration: {{ duration }}h.',
    'lesson_cancelled': 'DriveSmart: Lesson on {{ date }} at {{ time }} cancelled by {{ cancelled_by }}.',
    'feedback_received': 'DriveSmart: New feedback from {{ instructor_name }} – Rating: {{ rating }}/5.',
    'payment_success': 'DriveSmart: Payment of £{{ amount }} confirmed for lesson on {{ date }}.',
    'skill_updated': 'DriveSmart: Skill update – {{ skill_name }}: {{ status }}.',
    'lesson_rescheduled': 'DriveSmart: Lesson rescheduled from {{ old_date }} to {{ new_date }} at {{ new_time }}.',
    'refund_requested': 'DriveSmart: Refund requested – £{{ amount }} by {{ student_name }}.',
    'refund_processed': 'DriveSmart: Refund £{{ amount }} {{ status }}.',
    'package_purchased': 'DriveSmart: Block booking confirmed! {{ total_lessons }} lessons – {{ discount_percent }}% off. Total: £{{ total_price }}.',
    'lesson_reminder': 'DriveSmart: Reminder – lesson on {{ date }} at {{ time }} with {{ instructor_name }}. Be ready!',
    'review_received': 'DriveSmart: New review from {{ student_name }} – {{ rating }}/5.',
    'payout_processed': 'DriveSmart: Payout of £{{ amount }} {{ status }}. Check your dashboard for details.',
}

# ── In-App Notification Category Map ─────────────────────────────

INAPP_CATEGORY_MAP = {
    'welcome': 'success',
    'lesson_booked': 'success',
    'lesson_cancelled': 'danger',
    'feedback_received': 'info',
    'payment_success': 'success',
    'skill_updated': 'info',
    'lesson_rescheduled': 'warning',
    'refund_requested': 'warning',
    'refund_processed': 'info',
    'package_purchased': 'success',
    'lesson_reminder': 'warning',
    'review_received': 'info',
    'payout_processed': 'success',
}


def _render(template_str, **kwargs):
    """Render a Jinja2 template string with context."""
    try:
        return render_template_string(template_str, **kwargs)
    except Exception as e:
        logger.error(f'Template render error: {e}')
        return template_str


# ── Send Functions ───────────────────────────────────────────────

def send_email(recipient_email, template_key, **kwargs):
    """Send an email notification using Flask-Mail."""
    if not current_app.config.get('MAIL_ENABLED'):
        logger.debug(f'Email disabled, skipping: {template_key} to {recipient_email}')
        return False

    template = EMAIL_TEMPLATES.get(template_key)
    if not template:
        logger.error(f'Unknown email template: {template_key}')
        return False

    try:
        mail = current_app.extensions.get('mail')
        if not mail:
            logger.warning('Flask-Mail not initialised')
            return False

        subject = _render(template['subject'], **kwargs)
        body = _render(template['body'], **kwargs)

        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            body=body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@drivesmart.com')
        )
        mail.send(msg)
        logger.info(f'Email sent: {template_key} → {recipient_email}')
        return True
    except Exception as e:
        logger.error(f'Email send failed ({template_key} → {recipient_email}): {e}')
        return False


def send_whatsapp(phone_number, template_key, **kwargs):
    """Send a WhatsApp notification via Twilio."""
    if not current_app.config.get('WHATSAPP_ENABLED'):
        logger.debug(f'WhatsApp disabled, skipping: {template_key} to {phone_number}')
        return False

    template_str = WHATSAPP_TEMPLATES.get(template_key)
    if not template_str:
        logger.error(f'Unknown WhatsApp template: {template_key}')
        return False

    try:
        from twilio.rest import Client
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID', '').strip('"\' ')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN', '').strip('"\' ')
        from_number = current_app.config.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')

        if not account_sid or not auth_token or \
           account_sid.startswith('your-') or auth_token.startswith('your-'):
            logger.warning('Twilio credentials not configured — update TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN')
            return False

        body = _render(template_str, **kwargs)

        # Ensure WhatsApp prefix
        to_number = phone_number.strip()
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )
        logger.info(
            f'WhatsApp sent: {template_key} → {phone_number} '
            f'(sid: {message.sid})'
        )
        return True
    except Exception as e:
        logger.error(f'WhatsApp send failed ({template_key} → {phone_number}): {e}')
        return False


def send_sms(phone_number, template_key, **kwargs):
    """Send an SMS notification via Twilio."""
    if not current_app.config.get('SMS_ENABLED'):
        logger.debug(f'SMS disabled, skipping: {template_key} to {phone_number}')
        return False

    template_str = SMS_TEMPLATES.get(template_key)
    if not template_str:
        logger.error(f'Unknown SMS template: {template_key}')
        return False

    try:
        from twilio.rest import Client
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID', '').strip('"\' ')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN', '').strip('"\' ')
        from_number = current_app.config.get('TWILIO_SMS_FROM', '').strip('"\' ')

        if not account_sid or not auth_token or not from_number or \
           account_sid.startswith('your-') or auth_token.startswith('your-'):
            logger.warning('Twilio SMS credentials not configured')
            return False

        body = _render(template_str, **kwargs)
        to_number = phone_number.strip()

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )
        logger.info(f'SMS sent: {template_key} → {phone_number} (sid: {message.sid})')
        return True
    except Exception as e:
        logger.error(f'SMS send failed ({template_key} → {phone_number}): {e}')
        return False


def create_in_app_notification(user_id, template_key, link=None, **kwargs):
    """Create an in-app notification record in the database."""
    from app.models import InAppNotification
    from app import db

    email_template = EMAIL_TEMPLATES.get(template_key)
    title = _render(email_template['subject'], **kwargs) if email_template else template_key.replace('_', ' ').title()

    sms_template = SMS_TEMPLATES.get(template_key)
    message = _render(sms_template, **kwargs) if sms_template else title

    category = INAPP_CATEGORY_MAP.get(template_key, 'info')

    try:
        notif = InAppNotification(
            user_id=user_id,
            title=title,
            message=message,
            category=category,
            link=link,
        )
        db.session.add(notif)
        db.session.commit()
        logger.info(f'In-app notification created: {template_key} for user {user_id}')
        return True
    except Exception as e:
        logger.error(f'In-app notification failed ({template_key} for user {user_id}): {e}')
        return False


# ── High-level Notification Dispatcher ───────────────────────────

def notify_user(user, template_key, **kwargs):
    """
    Send notification to a user based on their preferences.
    Sends via email, WhatsApp, SMS, and always creates an in-app notification.
    """
    from app.models import NotificationPreference

    pref = NotificationPreference.query.filter_by(user_id=user.id).first()

    # Defaults: email on, whatsapp/sms off
    send_email_flag = pref.email_enabled if pref else True
    send_wa_flag = pref.whatsapp_enabled if pref else False
    send_sms_flag = getattr(pref, 'sms_enabled', False) if pref else False

    results = {'email': False, 'whatsapp': False, 'sms': False, 'in_app': False}

    # Always create in-app notification
    results['in_app'] = create_in_app_notification(
        user.id, template_key, **kwargs
    )

    if send_email_flag and user.email:
        results['email'] = send_email(user.email, template_key, **kwargs)

    phone = _get_user_phone(user)

    if send_wa_flag and phone:
        results['whatsapp'] = send_whatsapp(phone, template_key, **kwargs)
    elif send_wa_flag:
        logger.warning(f'WhatsApp enabled but no phone for user {user.id}')

    if send_sms_flag and phone:
        results['sms'] = send_sms(phone, template_key, **kwargs)
    elif send_sms_flag:
        logger.warning(f'SMS enabled but no phone for user {user.id}')

    return results


def _get_user_phone(user):
    """Get phone number for a user from their profile."""
    if user.is_student() and user.student_profile:
        return user.student_profile.phone
    if user.is_instructor() and user.instructor_profile:
        return getattr(user.instructor_profile, 'phone', None)
    return None
