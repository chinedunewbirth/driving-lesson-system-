from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import current_user
from app.ai_chatbot import AIChatBot
from app.forms import ChatbotForm
import logging

bp = Blueprint('chatbot', __name__)

# Initialize chatbot (consider moving to app factory for better testing)
chatbot = AIChatBot()

logger = logging.getLogger(__name__)


@bp.route('/chatbot', methods=['GET', 'POST'])
def chatbot_page():
    """Render the chatbot interface"""
    form = ChatbotForm()
    return render_template('chatbot.html', form=form)


@bp.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat API requests"""
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

        # Get user ID for conversation context
        user_id = str(current_user.id) if current_user.is_authenticated else None

        # Check rate limiting (implement proper rate limiting in production)
        if _is_rate_limited(user_id):
            return jsonify({
                'error': 'Rate limited',
                'response': 'You\'re sending messages too quickly. Please wait a moment before trying again.'
            }), 429

        # Get AI response
        use_ai = current_app.config.get('USE_AI_CHATBOT', True)
        result = chatbot.get_response(user_message, user_id, use_ai=use_ai)

        # Log the interaction
        logger.info(
            f"Chat interaction - User: {user_id}, "
            f"Intent: {result.get('intent')}, "
            f"Confidence: {result.get('confidence', 0):.2f}"
        )

        return jsonify({
            'response': result['response'],
            'intent': result.get('intent'),
            'confidence': result.get('confidence', 0.0)
        })

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'response': (
                'I apologize, but I\'m experiencing technical difficulties. '
                'Please try again later or contact support.'
            )
        }), 500


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


def _is_rate_limited(user_id: str) -> bool:
    """Basic rate limiting - implement proper rate limiting in production"""
    # This is a placeholder - use Redis or similar for production rate limiting
    return False
