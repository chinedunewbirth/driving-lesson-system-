import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta, timezone, time as dt_time
import re

from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation context and history"""

    def __init__(self, redis_client=None, max_history=10):
        self.redis = redis_client
        self.max_history = max_history

        # Try to get redis from Flask app if not provided
        if self.redis is None:
            try:
                from flask import current_app
                if hasattr(current_app, 'redis') and current_app.redis:
                    self.redis = current_app.redis
            except Exception:
                pass

    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """Retrieve conversation history for a user"""
        if not self.redis:
            return []

        try:
            history = self.redis.get(f"chat_history:{user_id}")
            return json.loads(history) if history else []
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []

    def add_message(self, user_id: str, message: Dict):
        """Add a message to conversation history"""
        if not self.redis:
            return

        try:
            history = self.get_conversation_history(user_id)
            history.append(message)

            # Keep only recent messages
            if len(history) > self.max_history:
                history = history[-self.max_history:]

            self.redis.setex(
                f"chat_history:{user_id}",
                timedelta(hours=24),  # Expire after 24 hours
                json.dumps(history)
            )
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")


class IntentClassifier:
    """Rule-based intent classification with actionable intents"""

    def __init__(self):
        self.intents = {
            'reschedule_lesson': [
                r'reschedule', r'change.*(?:date|time|lesson)',
                r'move\s*(?:my\s*)?lesson', r'different\s*(?:date|time)',
                r'postpone', r'shift\s*(?:my\s*)?lesson',
            ],
            'cancel_lesson': [
                r'cancel.*lesson', r'cancel\s*(?:my\s*)?(?:booking|appointment)',
                r'don\'?t\s*want.*lesson',
            ],
            'book_lesson': [
                r'book.*lesson', r'(?<!\w)schedule.*lesson', r'make.*appointment',
                r'book.*appointment', r'i\s*want\s*to\s*book',
                r'book\s*a?\s*(?:new\s*)?lesson', r'reserve.*slot',
                r'can\s*(?:i|you).*book', r'set\s*up.*lesson',
            ],
            'refund': [
                r'refund', r'money\s*back', r'get.*(?:my\s*)?money',
                r'reimburse', r'chargeback',
            ],
            'find_instructor': [
                r'(?:find|search|closest|near(?:by|est)?)\s*instructor',
                r'instructor.*(?:near|close|around|location|area)',
                r'who.*(?:teach|available).*(?:near|in\s+\w+)',
                r'instructor.*(?:in|at|around)\s+\w+',
                r'driving.*(?:teacher|instructor).*near',
            ],
            'view_lessons': [
                r'(?:my|upcoming|next)\s*lesson', r'show.*lesson',
                r'when.*(?:my|next).*lesson', r'lesson.*schedule',
                r'what.*(?:booked|scheduled)',
            ],
            'available_slots': [
                r'(?:available|free|open)\s*(?:time|slot|hour)',
                r'when.*(?:available|free)', r'what\s*time',
            ],
            'pricing': [
                r'how\s*much', r'cost', r'price', r'rate',
                r'fee', r'charge', r'pricing',
            ],
            'requirements': [
                r'what.*need', r'what.*bring', r'requirement',
                r'preparation', r'before.*lesson', r'first.*lesson',
            ],
            'contact': [
                r'contact', r'phone', r'email', r'call',
                r'reach', r'support',
            ],
            'progress': [
                r'progress', r'skill', r'how\s*am\s*i\s*doing',
                r'improvement', r'feedback',
            ],
        }

    def classify_intent(self, message: str) -> Tuple[str, float]:
        message_lower = message.lower()
        for intent, patterns in self.intents.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent, 0.85
        return 'general', 0.0

    # Actionable intents that trigger real operations
    ACTIONABLE_INTENTS = {
        'book_lesson', 'reschedule_lesson', 'cancel_lesson',
        'refund', 'find_instructor', 'view_lessons', 'available_slots',
    }


class AIChatBot:
    """AI-powered chatbot with action execution capabilities"""

    def __init__(self, redis_client=None):
        self.conversation_manager = ConversationManager(redis_client)
        self.intent_classifier = IntentClassifier()

        api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=api_key) if api_key else None

        self.fallback_responses = {
            'book_lesson': (
                "I can help you book a lesson! To proceed, I need:\n"
                "- **Preferred date** (e.g. next Monday, March 30)\n"
                "- **Preferred time** (e.g. 10:00 AM)\n"
                "- **Instructor** (name or 'any')\n"
                "- **Duration** (default 1 hour)\n\n"
                "You can also say something like: *Book a lesson with Sarah on Monday at 2pm*"
            ),
            'reschedule_lesson': (
                "I can reschedule your lesson. Let me show you your upcoming lessons so you can pick one to reschedule."
            ),
            'cancel_lesson': (
                "I can help cancel a lesson. Let me show you your upcoming lessons."
            ),
            'refund': (
                "I can help with a refund request. Let me check your eligible payments."
            ),
            'find_instructor': (
                "I'll help you find instructors near you! Please share your location or area name "
                "(e.g. *Find instructors near Manchester* or *instructors in London*)."
            ),
            'view_lessons': (
                "Let me pull up your upcoming lessons."
            ),
            'available_slots': (
                "I can check available slots. Which instructor and date would you like me to check?"
            ),
            'pricing': (
                "Our standard lesson rate is **£35/hour**. Rates vary by instructor — "
                "I can show you instructors and their rates if you'd like. "
                "We also offer block booking discounts:\n"
                "- 5 lessons → 5% off\n- 10 lessons → 10% off\n- 20 lessons → 15% off"
            ),
            'requirements': (
                "For your first lesson, bring:\n"
                "- Valid **provisional driving licence**\n"
                "- Comfortable shoes and clothing\n"
                "- Glasses/contacts if needed\n\n"
                "Your instructor will handle everything else!"
            ),
            'contact': (
                "You can reach support at **support@drivesmart.co.uk** "
                "or use this AI assistant for most tasks."
            ),
            'progress': (
                "You can view your driving skills progress and lesson feedback "
                "on your **Progress** page. Would you like me to take you there?"
            ),
            'general': (
                "I'm your DriveSmart AI assistant! I can help you:\n"
                "- 📅 **Book** or **reschedule** lessons\n"
                "- 🏫 **Find instructors** near you\n"
                "- 💰 Request **refunds**\n"
                "- 📋 View your **upcoming lessons**\n"
                "- ❓ Answer questions about pricing, requirements, etc.\n\n"
                "What would you like to do?"
            ),
        }

    def get_response(self, message: str, user_id: Optional[str] = None,
                     use_ai: bool = True) -> Dict:
        """Get a response, potentially with an action to execute."""
        try:
            intent, confidence = self.intent_classifier.classify_intent(message.lower())

            # Build conversation context
            context = ""
            if user_id:
                history = self.conversation_manager.get_conversation_history(user_id)
                if history:
                    recent = history[-3:]
                    context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

            # Determine if this is an actionable request
            action_data = None
            if intent in IntentClassifier.ACTIONABLE_INTENTS and user_id:
                action_data = self._extract_action_params(message, intent, user_id)

            # Get response text
            if use_ai and self.openai_client:
                ai_response = self._get_ai_response(message, intent, context, confidence, action_data)
                response = ai_response or self.fallback_responses.get(intent, self.fallback_responses['general'])
            else:
                response = self.fallback_responses.get(intent, self.fallback_responses['general'])

            # Store conversation
            if user_id:
                self.conversation_manager.add_message(user_id, {
                    'role': 'user', 'content': message,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                self.conversation_manager.add_message(user_id, {
                    'role': 'assistant', 'content': response,
                    'intent': intent, 'confidence': confidence,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

            result = {
                'response': response,
                'intent': intent,
                'confidence': confidence,
            }

            if action_data:
                result['action'] = action_data

            return result

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                'response': "I apologize, but I'm experiencing technical difficulties. Please try again.",
                'intent': 'error',
                'confidence': 0.0,
            }

    def _extract_action_params(self, message: str, intent: str, user_id: str) -> Optional[Dict]:
        """Extract structured action parameters from a user message."""
        msg = message.lower()

        if intent == 'view_lessons':
            return {'type': 'view_lessons'}

        if intent == 'find_instructor':
            # Try to extract location text
            location = None
            patterns = [
                r'(?:near|in|at|around)\s+([a-zA-Z\s]+?)(?:\s*$|\s*\.|,)',
                r'instructors?\s+(?:near|in|at|around)\s+([a-zA-Z\s]+)',
            ]
            for p in patterns:
                m = re.search(p, message, re.IGNORECASE)
                if m:
                    location = m.group(1).strip()
                    break
            return {'type': 'find_instructor', 'location': location}

        if intent == 'refund':
            return {'type': 'list_refundable'}

        if intent == 'reschedule_lesson':
            return {'type': 'list_reschedulable'}

        if intent == 'cancel_lesson':
            return {'type': 'list_cancellable'}

        if intent == 'book_lesson':
            params = {'type': 'book_lesson'}
            # Try extract instructor name
            m = re.search(r'(?:with|instructor)\s+([a-zA-Z_]+)', message, re.IGNORECASE)
            if m:
                params['instructor_name'] = m.group(1).strip()
            # Try extract date
            params['date'] = self._parse_date(message)
            # Try extract time
            params['time'] = self._parse_time(message)
            # Try extract duration
            dm = re.search(r'(\d+)\s*(?:hour|hr|h)', msg)
            if dm:
                params['duration'] = int(dm.group(1))
            return params

        if intent == 'available_slots':
            params = {'type': 'available_slots'}
            m = re.search(r'(?:for|with|instructor)\s+([a-zA-Z_]+)', message, re.IGNORECASE)
            if m:
                params['instructor_name'] = m.group(1).strip()
            params['date'] = self._parse_date(message)
            return params

        return None

    def _parse_date(self, message: str) -> Optional[str]:
        """Extract a date from natural language."""
        msg = message.lower()
        today = date.today()

        if 'today' in msg:
            return today.isoformat()
        if 'tomorrow' in msg:
            return (today + timedelta(days=1)).isoformat()

        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if day in msg:
                prefix = 'next' in msg
                current_day = today.weekday()
                diff = (i - current_day) % 7
                if diff == 0:
                    diff = 7 if prefix else 0
                elif prefix and diff <= 7:
                    diff += 7 if diff <= (7 - current_day) else 0
                if diff == 0:
                    diff = 7
                return (today + timedelta(days=diff)).isoformat()

        # Try explicit date formats
        for pattern, fmt in [
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', None),
            (r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?', 'month_name'),
        ]:
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                try:
                    if fmt == 'month_name':
                        month_str = m.group(1)
                        day_num = int(m.group(2))
                        year = int(m.group(3)) if m.group(3) else today.year
                        d = datetime.strptime(f"{month_str} {day_num} {year}", "%B %d %Y").date()
                    else:
                        d = datetime.strptime(f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%d/%m/%Y").date()
                    return d.isoformat()
                except ValueError:
                    pass
        return None

    def _parse_time(self, message: str) -> Optional[str]:
        """Extract a time from natural language."""
        # Match patterns like 2pm, 10:30am, 14:00
        patterns = [
            (r'(\d{1,2}):(\d{2})\s*(am|pm)', 'ampm'),
            (r'(\d{1,2})\s*(am|pm)', 'ampm_short'),
            (r'(\d{1,2}):(\d{2})', '24h'),
        ]
        for pattern, fmt in patterns:
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                try:
                    if fmt == 'ampm':
                        t = datetime.strptime(f"{m.group(1)}:{m.group(2)} {m.group(3)}", "%I:%M %p").time()
                    elif fmt == 'ampm_short':
                        t = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%I %p").time()
                    else:
                        t = datetime.strptime(f"{m.group(1)}:{m.group(2)}", "%H:%M").time()
                    return t.strftime('%H:%M')
                except ValueError:
                    pass
        return None

    def _get_ai_response(self, message: str, intent: str, context: str,
                         confidence: float, action_data: Optional[Dict] = None) -> Optional[str]:
        """Get response from OpenAI API with action awareness."""
        try:
            action_context = ""
            if action_data:
                action_context = f"\nDetected action: {json.dumps(action_data)}\nAcknowledge the action and guide the user. Be specific about what will happen."

            system_prompt = f"""You are DriveSmart's AI assistant for a UK driving school platform.
You can ACTUALLY perform these actions for logged-in students:
- Book driving lessons with specific instructors, dates, and times
- Reschedule existing lessons to new dates/times
- Cancel upcoming lessons
- Request refunds for payments
- Find nearby instructors by location
- Show upcoming lessons and available time slots

Current intent: {intent} (confidence: {confidence:.0%})
{action_context}
Recent conversation: {context}

Guidelines:
- Be concise, friendly, and action-oriented
- When an action is detected, confirm what you're about to do
- Use UK English and GBP (£) for prices
- Standard lesson rate is £35/hour
- If parameters are missing, ask for them specifically
- Format responses with markdown for readability
- Always prioritise safety"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=300,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None

    def get_conversation_stats(self, user_id: str) -> Dict:
        """Get statistics about user's conversation"""
        history = self.conversation_manager.get_conversation_history(user_id)
        if not history:
            return {'total_messages': 0, 'intents': {}, 'avg_confidence': 0.0}

        intents = {}
        confidences = []

        for msg in history:
            if msg.get('role') == 'assistant':
                intent = msg.get('intent', 'unknown')
                intents[intent] = intents.get(intent, 0) + 1
                if 'confidence' in msg:
                    confidences.append(msg['confidence'])

        # Simple average calculation without numpy
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            'total_messages': len(history),
            'intents': intents,
            'avg_confidence': avg_confidence
        }
