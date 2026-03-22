import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import re

import openai

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
    """Simple rule-based intent classification"""

    def __init__(self):
        # Define intents and their patterns
        self.intents = {
            'booking': [
                r'book.*lesson', r'schedule.*lesson', r'make.*appointment',
                r'book.*appointment', r'schedule.*appointment', r'reserve'
            ],
            'pricing': [
                r'how.*much', r'cost', r'price', r'rate', r'fee', r'charge', r'pricing'
            ],
            'cancellation': [
                r'cancel', r'reschedule', r'change.*time', r'modify.*booking'
            ],
            'requirements': [
                r'what.*need', r'what.*bring', r'requirement', r'preparation',
                r'before.*lesson', r'first.*lesson'
            ],
            'contact': [
                r'contact', r'phone', r'email', r'call', r'reach', r'support'
            ]
        }

    def classify_intent(self, message: str) -> Tuple[str, float]:
        """Classify the intent of a message using regex patterns"""
        message_lower = message.lower()

        for intent, patterns in self.intents.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent, 0.8  # High confidence for regex matches

        return 'unknown', 0.0


class AIChatBot:
    """AI-powered chatbot with OpenAI integration and rule-based fallback"""

    def __init__(self, redis_client=None):
        # Initialize components
        self.conversation_manager = ConversationManager(redis_client)
        self.intent_classifier = IntentClassifier()

        # Configure OpenAI
        openai.api_key = os.getenv('OPENAI_API_KEY')

        # Fallback responses
        self.fallback_responses = {
            'booking': (
                "To book a lesson, log in to your student account and "
                "visit the 'Book Lesson' section. You can choose from "
                "available instructors and time slots."
            ),
            'pricing': (
                "Our lesson prices vary by instructor. You can view "
                "hourly rates when booking a lesson or check instructor profiles."
            ),
            'cancellation': (
                "You can cancel or reschedule lessons through your "
                "dashboard, subject to our 24-hour cancellation policy."
            ),
            'requirements': (
                "For your first lesson, bring a valid learner's permit, "
                "wear comfortable clothing, and be ready to learn. "
                "Safety is our top priority!"
            ),
            'contact': (
                "You can reach our support team at "
                "support@drivingschool.com or call us at (555) 123-DRIVE."
            ),
            'unknown': (
                "I'm here to help with driving lessons! Try asking about "
                "booking, pricing, requirements, or contact information."
            )
        }

    def get_response(self, message: str, user_id: Optional[str] = None,
                     use_ai: bool = True) -> Dict[str, str]:
        """
        Get a response to a user message

        Args:
            message: User's message
            user_id: User identifier for conversation context
            use_ai: Whether to use AI backend or fallback to rules

        Returns:
            Dict with 'response' and 'intent' keys
        """
        try:
            # Classify intent
            intent, confidence = self.intent_classifier.classify_intent(message.lower())

            # Get conversation context
            context = ""
            if user_id:
                history = self.conversation_manager.get_conversation_history(user_id)
                if history:
                    recent_messages = history[-3:]  # Last 3 messages for context
                    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])

            # Try AI response first if enabled
            if use_ai and openai.api_key:
                ai_response = self._get_ai_response(message, intent, context, confidence)
                if ai_response:
                    response = ai_response
                else:
                    response = self.fallback_responses.get(intent, self.fallback_responses['unknown'])
            else:
                response = self.fallback_responses.get(intent, self.fallback_responses['unknown'])

            # Store conversation if user_id provided
            if user_id:
                self.conversation_manager.add_message(user_id, {
                    'role': 'user',
                    'content': message,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                self.conversation_manager.add_message(user_id, {
                    'role': 'assistant',
                    'content': response,
                    'intent': intent,
                    'confidence': confidence,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

            return {
                'response': response,
                'intent': intent,
                'confidence': confidence
            }

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                'response': (
                    "I apologize, but I'm experiencing technical difficulties. "
                    "Please contact support@drivingschool.com for assistance."
                ),
                'intent': 'error',
                'confidence': 0.0
            }

    def _get_ai_response(self, message: str, intent: str, context: str,
                         confidence: float) -> Optional[str]:
        """Get response from OpenAI API"""
        try:
            system_prompt = f"""You are a helpful AI assistant for a driving school.
You help students with booking lessons, understanding requirements, pricing, and general driving questions.

Current user intent: {intent} (confidence: {confidence:.2f})
Conversation context: {context}

Guidelines:
- Be friendly and professional
- Focus on driving lessons and school services
- If unsure, direct to human support
- Keep responses concise but helpful
- Always prioritize safety

Respond naturally to: {message}"""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=150,
                temperature=0.7
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
