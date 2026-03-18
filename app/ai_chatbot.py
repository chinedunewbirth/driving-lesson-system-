import re

class ChatBot:
    def __init__(self):
        self.responses = {
            r'hello|hi|hey': 'Hello! How can I help you with driving lessons today?',
            r'how to book a lesson': 'To book a lesson, you need to be logged in as a student, then go to your dashboard and click "Book Lesson".',
            r'what are the prices': 'Our instructors have different hourly rates. You can see them when booking.',
            r'cancel lesson': 'You can cancel a lesson from your dashboard, up to 24 hours in advance.',
            r'thanks|thank you': 'You\'re welcome! If you have more questions, feel free to ask.',
            r'bye|goodbye': 'Goodbye! Safe driving!',
        }

    def get_response(self, message):
        message = message.lower()
        for pattern, response in self.responses.items():
            if re.search(pattern, message):
                return response
        return "I'm sorry, I don't understand. Please contact support at support@drivingschool.com."