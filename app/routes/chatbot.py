from flask import Blueprint, request, jsonify, render_template, current_app, url_for
from flask_login import current_user, login_required
from app.ai_chatbot import AIChatBot
from app.forms import ChatbotForm
from app import db
import logging
import secrets
import re as _re
from datetime import datetime

bp = Blueprint('chatbot', __name__)

chatbot = AIChatBot()

logger = logging.getLogger(__name__)


@bp.route('/chatbot', methods=['GET', 'POST'])
def chatbot_page():
    """Render the chatbot interface"""
    form = ChatbotForm()
    return render_template('chatbot.html', form=form)


@bp.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat API requests — now with action execution"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'error': 'Message is required',
                'response': 'Please provide a message to continue our conversation.'
            }), 400

        user_message = data['message'].strip()
        if not user_message:
            return jsonify({
                'error': 'Empty message',
                'response': 'Please type a message to chat with me.'
            }), 400

        user_id = str(current_user.id) if current_user.is_authenticated else None

        if _is_rate_limited(user_id):
            return jsonify({
                'error': 'Rate limited',
                'response': "You're sending messages too quickly. Please wait a moment."
            }), 429

        use_ai = current_app.config.get('USE_AI_CHATBOT', True)
        result = chatbot.get_response(user_message, user_id, use_ai=use_ai)

        # If there's an actionable intent, execute it
        action = result.get('action')
        action_result = None
        if action and current_user.is_authenticated:
            user_role = current_user.role  # 'student', 'instructor', or 'admin'
            action_result = _execute_action(action, current_user.id, user_role)

        logger.info(
            f"Chat interaction - User: {user_id}, "
            f"Intent: {result.get('intent')}, "
            f"Confidence: {result.get('confidence', 0):.2f}, "
            f"Action: {action.get('type') if action else 'none'}"
        )

        response_data = {
            'response': result['response'],
            'intent': result.get('intent'),
            'confidence': result.get('confidence', 0.0),
        }

        if action_result:
            response_data['action_result'] = action_result

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'response': 'I apologize, but I\'m experiencing technical difficulties.'
        }), 500


@bp.route('/api/chat/action', methods=['POST'])
@login_required
def chat_action():
    """Execute a confirmed chatbot action (book, reschedule, refund, cancel)."""
    if not current_user.is_student():
        return jsonify({'error': 'Only students can perform actions.'}), 403

    data = request.get_json()
    if not data or 'action' not in data:
        return jsonify({'error': 'Action required'}), 400

    action_type = data['action']
    user_id = current_user.id

    try:
        from app.chatbot_actions import (
            book_lesson, reschedule_lesson, request_refund,
        )
        from app.models import Lesson, User
        from datetime import datetime, date

        if action_type == 'confirm_book':
            instructor_id = data.get('instructor_id')
            lesson_date = datetime.strptime(data['date'], '%Y-%m-%d').date() if data.get('date') else None
            lesson_time = datetime.strptime(data['time'], '%H:%M').time() if data.get('time') else None
            duration = data.get('duration', 1)
            pickup = data.get('pickup_address')

            if not instructor_id or not lesson_date or not lesson_time:
                return jsonify({'error': 'Instructor, date, and time are required.'}), 400

            result = book_lesson(user_id, instructor_id, lesson_date, lesson_time, duration, pickup)
            return jsonify(result)

        elif action_type == 'confirm_reschedule':
            lesson_id = data.get('lesson_id')
            new_date = datetime.strptime(data['new_date'], '%Y-%m-%d').date() if data.get('new_date') else None
            new_time = datetime.strptime(data['new_time'], '%H:%M').time() if data.get('new_time') else None
            reason = data.get('reason', 'Rescheduled via AI assistant')

            if not lesson_id or not new_date or not new_time:
                return jsonify({'error': 'Lesson ID, new date, and new time are required.'}), 400

            result = reschedule_lesson(user_id, lesson_id, new_date, new_time, reason)
            return jsonify(result)

        elif action_type == 'confirm_refund':
            payment_id = data.get('payment_id')
            reason = data.get('reason', 'Requested via AI assistant')

            if not payment_id:
                return jsonify({'error': 'Payment ID is required.'}), 400

            result = request_refund(user_id, payment_id=payment_id, reason=reason)
            return jsonify(result)

        elif action_type == 'confirm_cancel':
            lesson_id = data.get('lesson_id')
            if not lesson_id:
                return jsonify({'error': 'Lesson ID is required.'}), 400

            lesson = Lesson.query.get(lesson_id)
            if not lesson or lesson.student_id != user_id:
                return jsonify({'success': False, 'message': 'Lesson not found.'}), 404
            if lesson.status != 'confirmed':
                return jsonify({'success': False, 'message': 'Only confirmed lessons can be cancelled.'})
            if lesson.date and lesson.date < date.today():
                return jsonify({'success': False, 'message': 'Past lessons cannot be cancelled.'})

            lesson.status = 'cancelled'
            db.session.commit()

            instructor = User.query.get(lesson.instructor_id)
            if instructor:
                from app.notifications import notify_user
                try:
                    notify_user(instructor, 'lesson_cancelled', **{
                        'recipient_name': instructor.username,
                        'cancelled_by': current_user.username,
                        'date': lesson.date.strftime('%b %d, %Y') if lesson.date else 'N/A',
                        'time': lesson.time.strftime('%I:%M %p') if lesson.time else 'N/A',
                    })
                except Exception:
                    pass

            return jsonify({'success': True, 'message': 'Lesson cancelled successfully.'})

        else:
            return jsonify({'error': f'Unknown action: {action_type}'}), 400

    except Exception as e:
        logger.error(f"Chat action error: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Action failed. Please try again.'}), 500


@bp.route('/api/chat/stats', methods=['GET'])
def chat_stats():
    """Get conversation statistics for the current user"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        stats = chatbot.get_conversation_stats(str(current_user.id))
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting chat stats: {e}")
        return jsonify({'error': 'Could not retrieve statistics'}), 500


def _execute_action(action, user_id, user_role='student'):
    """Execute a chatbot action and return structured results for the UI."""
    from app.chatbot_actions import (
        get_upcoming_lessons, find_nearby_instructors,
        get_refundable_payments, get_available_slots,
    )
    from app.models import User
    from datetime import datetime

    action_type = action.get('type')

    try:
        if action_type == 'view_lessons':
            lessons = get_upcoming_lessons(user_id, role=user_role)
            empty_msg = 'No upcoming lessons found.'
            if user_role == 'student':
                empty_msg += ' Would you like to book one?'
            return {
                'type': 'lesson_list',
                'title': 'Your Upcoming Lessons',
                'items': lessons,
                'empty_message': empty_msg,
            }

        elif action_type == 'find_instructor':
            location = action.get('location')
            instructors = find_nearby_instructors(location_text=location)
            return {
                'type': 'instructor_list',
                'title': f'Instructors{" near " + location if location else ""}',
                'items': instructors,
                'empty_message': 'No instructors found. Try a different location.',
            }

        elif action_type == 'list_refundable':
            payments = get_refundable_payments(user_id)
            return {
                'type': 'refund_list',
                'title': 'Eligible Payments for Refund',
                'items': payments,
                'empty_message': 'No payments eligible for refund at the moment.',
            }

        elif action_type in ('list_reschedulable', 'list_cancellable'):
            lessons = get_upcoming_lessons(user_id, role=user_role)
            label = 'Reschedule' if 'reschedule' in action_type else 'Cancel'
            return {
                'type': f'{label.lower()}_list',
                'title': f'Select a Lesson to {label}',
                'items': lessons,
                'empty_message': 'No upcoming lessons to modify.',
            }

        elif action_type == 'book_lesson':
            # Return instructor list for selection, with any pre-filled params
            result = {
                'type': 'book_form',
                'title': 'Book a Lesson',
                'prefill': {},
            }
            if action.get('instructor_name'):
                inst = User.query.filter(
                    User.username.ilike(f"%{action['instructor_name']}%"),
                    User.role == 'instructor'
                ).first()
                if inst:
                    result['prefill']['instructor_id'] = inst.id
                    result['prefill']['instructor_name'] = inst.username
            if action.get('date'):
                result['prefill']['date'] = action['date']
            if action.get('time'):
                result['prefill']['time'] = action['time']
            if action.get('duration'):
                result['prefill']['duration'] = action['duration']

            from app.chatbot_actions import find_nearby_instructors
            result['instructors'] = find_nearby_instructors()
            return result

        elif action_type == 'available_slots':
            instructor_name = action.get('instructor_name')
            date_str = action.get('date')

            if not instructor_name or not date_str:
                return {
                    'type': 'need_info',
                    'message': 'Please specify an instructor name and date to check slots.',
                }

            inst = User.query.filter(
                User.username.ilike(f"%{instructor_name}%"),
                User.role == 'instructor'
            ).first()
            if not inst:
                return {'type': 'need_info', 'message': f'Instructor "{instructor_name}" not found.'}

            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            slots = get_available_slots(inst.id, target_date)
            return {
                'type': 'slot_list',
                'title': f'Available slots for {inst.username} on {target_date.strftime("%b %d, %Y")}',
                'instructor_id': inst.id,
                'instructor_name': inst.username,
                'date': date_str,
                'slots': slots,
                'empty_message': f'No available slots for {inst.username} on that date.',
            }

    except Exception as e:
        logger.error(f"Action execution error: {e}")
        return {'type': 'error', 'message': 'Failed to execute action. Please try again.'}

    return None


# ── Registration AI Assistant (no login required) ────────────────

REGISTRATION_SYSTEM_PROMPT = """You are DriveSmart's friendly registration assistant for a UK driving school platform.
Your ONLY job is to help visitors complete the registration form. You do NOT book lessons or perform actions.

You can help with:
- Explaining the difference between Student and Instructor roles
- Advising on password strength (min 6 chars, mix of letters/numbers/symbols)
- Explaining why we need an address (for matching with nearby instructors)
- Describing what happens after registration (email confirmation link)
- Answering general questions about DriveSmart (pricing is £35/hour, block discounts available)
- Explaining what a provisional licence is and when they need it
- Reassuring about data privacy and security

Guidelines:
- Be concise, warm, and encouraging — max 2-3 sentences per response
- Use UK English and GBP (£)
- If asked about something unrelated to registration, gently redirect
- Never ask for or repeat passwords
- Format with markdown for readability"""

REGISTRATION_FALLBACK_RESPONSES = {
    'role': (
        "**Student** — You're learning to drive and want to book lessons with instructors.\n\n"
        "**Instructor** — You're a qualified driving instructor offering lessons to students.\n\n"
        "Most people register as a **Student**. You can always contact support to change later."
    ),
    'password': (
        "A strong password should be at least **6 characters** and include a mix of:\n"
        "- Uppercase and lowercase letters\n"
        "- Numbers\n"
        "- Special characters (!, @, #, etc.)\n\n"
        "The form will show you a strength indicator as you type."
    ),
    'address': (
        "We use your address to **match you with nearby driving instructors**. "
        "This helps us show you the most relevant instructors in your area. "
        "All fields are optional, but at least a city/postcode helps a lot!"
    ),
    'confirmation': (
        "After registering, you'll receive a **confirmation email** with a link. "
        "Click the link to verify your email, then you can log in and start booking lessons!"
    ),
    'pricing': (
        "Our standard lesson rate is **£35/hour**. We also offer block booking discounts:\n"
        "- 5 lessons → 5% off\n- 10 lessons → 10% off\n- 20 lessons → 15% off\n\n"
        "You'll be able to see instructor-specific rates after registering."
    ),
    'quick_register': (
        "**Quick registration** \u2014 just enter your email and phone number!\n\n"
        "We'll create your student account instantly, generate a secure password, "
        "and send a confirmation link to your inbox. Your phone number will be saved "
        "to your profile so instructors can contact you. Click **\u26a1 Quick Register** to start."
    ),
    'general': (
        "I'm here to help you sign up! I can explain:\n"
        "- 👤 **Student vs Instructor** roles\n"
        "- 🔒 **Password** requirements\n"
        "- 📍 Why we ask for your **address**\n"
        "- ✉️ The **email confirmation** process\n"
        "- 💷 **Pricing** and packages\n"
        "- ⚡ **Quick register** with just your email\n\n"
        "What would you like to know?"
    ),
}


def _classify_registration_intent(message):
    """Simple intent classification for registration questions."""
    import re
    msg = message.lower()
    patterns = {
        'quick_register': [r'quick', r'one.?click', r'fast.*regist', r'just.*email', r'easy.*sign', r'instant'],
        'role': [r'role', r'student.*instructor', r'instructor.*student', r'which.*choose', r'difference', r'what.*type'],
        'password': [r'password', r'strong', r'secure', r'characters?', r'how.*long'],
        'address': [r'address', r'location', r'postcode', r'city', r'why.*need.*address', r'where.*live'],
        'confirmation': [r'confirm', r'verification', r'email.*link', r'after.*register', r'what.*next', r'what.*happen'],
        'pricing': [r'price', r'cost', r'how\s*much', r'rate', r'fee', r'discount', r'package'],
    }
    for intent, pats in patterns.items():
        for p in pats:
            if re.search(p, msg):
                return intent
    return 'general'


@bp.route('/api/registration-assistant', methods=['POST'])
def registration_assistant():
    """AI assistant for the registration page — no login required."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'response': 'Please type a question about registration.'}), 400

        user_message = data['message'].strip()
        if not user_message or len(user_message) > 500:
            return jsonify({'response': 'Please enter a valid question (max 500 characters).'}), 400

        intent = _classify_registration_intent(user_message)

        # Try AI response if available
        use_ai = current_app.config.get('USE_AI_CHATBOT', True)
        api_key = current_app.config.get('OPENAI_API_KEY')

        if use_ai and api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": REGISTRATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=200,
                    temperature=0.7,
                )
                ai_text = response.choices[0].message.content.strip()
                if ai_text:
                    return jsonify({'response': ai_text, 'intent': intent})
            except Exception as e:
                logger.warning(f"Registration assistant AI error: {e}")

        # Fallback to rule-based
        fallback = REGISTRATION_FALLBACK_RESPONSES.get(
            intent, REGISTRATION_FALLBACK_RESPONSES['general']
        )
        return jsonify({'response': fallback, 'intent': intent})

    except Exception as e:
        logger.error(f"Registration assistant error: {e}")
        return jsonify({
            'response': "Sorry, I'm having trouble right now. Please try again or proceed with the form — all fields have helpful placeholders!"
        }), 500


@bp.route('/api/quick-register', methods=['POST'])
def quick_register():
    """One-click registration — requires email and phone number."""
    from app.models import User, StudentProfile
    from app.notifications import send_email

    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({'success': False, 'message': 'Email is required.'}), 400

        email = data['email'].strip().lower()
        phone = data.get('phone', '').strip()

        # Validate email format
        if not _re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400

        # Validate phone number (require it)
        if not phone:
            return jsonify({'success': False, 'message': 'Phone number is required.'}), 400

        # Accept UK-style phone numbers: digits, spaces, +, -, (, )
        cleaned_phone = _re.sub(r'[\s\-\(\)]', '', phone)
        if not _re.match(r'^\+?[0-9]{10,15}$', cleaned_phone):
            return jsonify({'success': False, 'message': 'Please enter a valid phone number (e.g. 07700 900123 or +447700900123).'}), 400

        # Check if email already exists
        existing = User.query.filter_by(email=email).first()
        if existing:
            return jsonify({
                'success': False,
                'message': 'An account with this email already exists. Please log in or use a different email.'
            }), 409

        # Auto-generate username from email prefix
        base_username = email.split('@')[0].replace('.', '_').replace('+', '_').lower()
        base_username = _re.sub(r'[^a-z0-9_]', '', base_username)[:20] or 'user'
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f'{base_username}_{counter}'
            counter += 1

        # Generate a secure random password
        temp_password = secrets.token_urlsafe(12)

        # Create user as student
        user = User(username=username, email=email, role='student')
        user.set_password(temp_password)
        db.session.add(user)
        db.session.commit()

        # Create student profile with phone number
        profile = StudentProfile(user_id=user.id, phone=phone)
        db.session.add(profile)
        db.session.commit()

        # Send confirmation email
        try:
            token = user.generate_confirmation_token()
            confirm_url = url_for('auth.confirm_email', token=token, _external=True)
            send_email(user.email, 'email_confirm', **{
                'username': username,
                'confirm_url': confirm_url,
            })
        except Exception as e:
            logger.warning(f"Quick-register email error: {e}")

        return jsonify({
            'success': True,
            'message': (
                f'Account created! A confirmation link has been sent to **{email}**. '
                f'Your username is **{username}** and your temporary password is **{temp_password}**. '
                f'Phone number **{phone}** saved to your profile. '
                'Please save these details and confirm your email to log in. '
                'You can change your password after logging in.'
            ),
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Quick-register error: {e}")
        return jsonify({
            'success': False,
            'message': 'Registration failed. Please try again or use the full form.'
        }), 500


def _is_rate_limited(user_id: str) -> bool:
    """Basic rate limiting placeholder."""
    return False
