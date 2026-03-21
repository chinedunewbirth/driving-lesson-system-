import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock
from app import create_app
from app.ai_chatbot import AIChatBot, IntentClassifier, ConversationManager
from config import TestingConfig

class TestIntentClassifier(unittest.TestCase):
    """Test intent classification functionality"""

    def setUp(self):
        self.classifier = IntentClassifier()

    def test_classify_booking_intent(self):
        """Test booking intent classification"""
        messages = [
            "How do I book a lesson?",
            "I want to schedule a driving lesson",
            "Book an appointment please"
        ]

        for message in messages:
            intent, confidence = self.classifier.classify_intent(message)
            self.assertEqual(intent, 'booking')
            self.assertGreater(confidence, 0.3)

    def test_classify_pricing_intent(self):
        """Test pricing intent classification"""
        messages = [
            "How much do lessons cost?",
            "What are your rates?",
            "Tell me about pricing"
        ]

        for message in messages:
            intent, confidence = self.classifier.classify_intent(message)
            self.assertEqual(intent, 'pricing')
            self.assertGreater(confidence, 0.3)

    def test_unknown_intent(self):
        """Test unknown intent handling"""
        message = "What's the weather like today?"
        intent, confidence = self.classifier.classify_intent(message)
        self.assertEqual(intent, 'unknown')

class TestConversationManager(unittest.TestCase):
    """Test conversation management functionality"""

    def setUp(self):
        self.redis_mock = Mock()
        self.manager = ConversationManager(self.redis_mock)

    def test_get_empty_history(self):
        """Test getting empty conversation history"""
        self.redis_mock.get.return_value = None
        history = self.manager.get_conversation_history("user123")
        self.assertEqual(history, [])

    def test_get_conversation_history(self):
        """Test getting conversation history"""
        mock_history = '[{"role": "user", "content": "Hello"}]'
        self.redis_mock.get.return_value = mock_history

        history = self.manager.get_conversation_history("user123")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['role'], 'user')

    def test_add_message(self):
        """Test adding message to conversation"""
        self.redis_mock.get.return_value = None

        message = {"role": "user", "content": "Hello"}
        self.manager.add_message("user123", message)

        # Verify Redis setex was called
        self.redis_mock.setex.assert_called_once()

class TestAIChatBot(unittest.TestCase):
    """Test AI chatbot functionality"""

    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Mock Redis
        self.redis_mock = Mock()
        self.chatbot = AIChatBot(self.redis_mock)

    def tearDown(self):
        self.app_context.pop()

    @patch('app.ai_chatbot.openai.ChatCompletion.create')
    def test_ai_response_success(self, mock_openai):
        """Test successful AI response"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "This is an AI response."
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_openai.return_value = mock_response

        result = self.chatbot.get_response("Hello", "user123", use_ai=True)

        self.assertIn('response', result)
        self.assertIn('intent', result)
        self.assertIn('confidence', result)

    def test_fallback_response(self):
        """Test fallback response when AI is disabled"""
        result = self.chatbot.get_response("How do I book a lesson?", use_ai=False)

        self.assertIn('book', result['response'].lower())
        self.assertEqual(result['intent'], 'booking')

    def test_error_handling(self):
        """Test error handling in chatbot"""
        # Test with invalid input
        result = self.chatbot.get_response("", "user123")

        self.assertIn('response', result)
        self.assertIn('intent', result)

    @patch('app.ai_chatbot.openai.ChatCompletion.create')
    def test_openai_error_fallback(self, mock_openai):
        """Test fallback when OpenAI API fails"""
        mock_openai.side_effect = Exception("API Error")

        result = self.chatbot.get_response("Hello", "user123", use_ai=True)

        # Should fall back to rule-based response
        self.assertIn('response', result)
        self.assertNotEqual(result['intent'], 'error')

    def test_conversation_stats(self):
        """Test conversation statistics"""
        # Mock conversation history
        mock_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!", "intent": "unknown", "confidence": 0.5},
            {"role": "user", "content": "Book a lesson"},
            {"role": "assistant", "content": "Sure!", "intent": "booking", "confidence": 0.8}
        ]

        self.redis_mock.get.return_value = str(mock_history).replace("'", '"')

        stats = self.chatbot.get_conversation_stats("user123")

        self.assertEqual(stats['total_messages'], 4)
        self.assertIn('booking', stats['intents'])
        self.assertIn('unknown', stats['intents'])

class TestChatbotIntegration(unittest.TestCase):
    """Integration tests for chatbot routes"""

    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_chat_api_endpoint(self):
        """Test chat API endpoint"""
        response = self.client.post('/api/chat', json={'message': 'Hello'})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('response', data)
        self.assertIn('intent', data)

    def test_chat_api_empty_message(self):
        """Test chat API with empty message"""
        response = self.client.post('/api/chat', json={'message': ''})

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)

    def test_chat_api_missing_message(self):
        """Test chat API with missing message"""
        response = self.client.post('/api/chat', json={})

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)

if __name__ == '__main__':
    unittest.main()