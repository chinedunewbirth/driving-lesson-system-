# Driving Lesson Management System

A complete, production-ready driving lesson management system using Flask, PostgreSQL, Docker, and GitHub Actions. The system includes role-based access (students, instructors, admin), lesson booking, and an AI-powered FAQ chatbot.

## Features

- **Role-based Authentication**: Separate dashboards for students, instructors, and administrators
- **Lesson Management**: Book, cancel, and manage driving lessons
- **AI-Powered Chatbot**: Intelligent FAQ assistant with conversation context
- **Modern AI Integration**: Uses OpenAI GPT models with intent classification
- **Real-time Communication**: WebSocket-based chat interface
- **Data Privacy**: GDPR-compliant conversation handling
- **Scalable Architecture**: Docker containerization with Redis caching

## Database Migrations

This project uses Alembic for database migrations. Migration files are retained in the repository to maintain database schema history and enable rollbacks. Do not delete migration files, as they are essential for database consistency and deployment.

To create a new migration:
```bash
flask db migrate -m "description"
```

To apply migrations:
```bash
flask db upgrade
```

To rollback:
```bash
flask db downgrade
```

## AI Features

### Intelligent Chatbot

The system includes a sophisticated AI chatbot that:

- **Intent Classification**: Uses sentence transformers to understand user intent
- **Context Awareness**: Maintains conversation history using Redis
- **AI-Powered Responses**: Integrates with OpenAI GPT models for natural responses
- **Fallback System**: Graceful degradation to rule-based responses
- **Privacy-First**: Conversations expire after 24 hours

### AI Configuration

Set the following environment variables:

```bash
OPENAI_API_KEY=your_openai_api_key_here
USE_AI_CHATBOT=true  # Set to false to use rule-based only
REDIS_URL=redis://localhost:6379/0
```

### AI Ethics & Safety

- All conversations are encrypted and stored temporarily
- No personal data is sent to AI services
- Fallback responses ensure service availability
- Rate limiting prevents abuse
- Comprehensive logging for monitoring

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key (optional, for AI features)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/driving-lesson-system.git
cd driving-lesson-system
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start the application:
```bash
docker-compose up -d
```

4. Run database migrations:
```bash
docker-compose exec web flask db upgrade
```

5. Access the application at `http://localhost:5000`

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/driving_school

# Security
SECRET_KEY=your-secret-key-change-in-production
SESSION_COOKIE_SECURE=true
REMEMBER_COOKIE_SECURE=true

# AI Features
OPENAI_API_KEY=your_openai_api_key
USE_AI_CHATBOT=true
ANTHROPIC_API_KEY=your_anthropic_key  # Alternative AI provider

# Redis
REDIS_URL=redis://redis:6379/0

# Rate Limiting
CHAT_RATE_LIMIT=60  # Messages per hour

# Logging
LOG_LEVEL=INFO
```

## Development

### Running Tests

```bash
# Run all tests
docker-compose exec web python -m pytest

# Run AI chatbot tests specifically
docker-compose exec web python -m pytest tests/test_ai_chatbot.py -v

# Run with coverage
docker-compose exec web python -m pytest --cov=app --cov-report=html
```

### Code Quality

```bash
# Lint code
docker-compose exec web flake8 app/

# Type checking
docker-compose exec web mypy app/

# Format code
docker-compose exec web black app/
```

### AI Model Updates

The chatbot uses pre-trained models. To update models:

```bash
# Update sentence transformers
docker-compose exec web python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2')"
```

## API Documentation

### Chatbot API

#### POST `/api/chat`
Send a message to the AI chatbot.

**Request:**
```json
{
  "message": "How do I book a lesson?"
}
```

**Response:**
```json
{
  "response": "To book a lesson, log in to your student account...",
  "intent": "booking",
  "confidence": 0.85
}
```

#### GET `/api/chat/stats`
Get conversation statistics for the authenticated user.

**Response:**
```json
{
  "total_messages": 24,
  "intents": {
    "booking": 8,
    "pricing": 5,
    "contact": 3
  },
  "avg_confidence": 0.72
}
```

## Deployment

### Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure HTTPS certificates
- [ ] Set `SESSION_COOKIE_SECURE=true`
- [ ] Configure proper database credentials
- [ ] Set up monitoring and logging
- [ ] Configure rate limiting
- [ ] Set up backup strategies
- [ ] Test AI fallback scenarios

### Docker Production

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  web:
    environment:
      - FLASK_ENV=production
      - USE_AI_CHATBOT=true
    secrets:
      - openai_key
```

## Security Considerations

### AI Security

- API keys are stored as environment variables
- Input validation prevents prompt injection
- Rate limiting prevents API abuse
- Conversation data expires automatically
- No sensitive user data sent to AI services

### Data Privacy

- Conversations stored temporarily in Redis
- Automatic cleanup after 24 hours
- No persistent storage of chat logs
- GDPR-compliant data handling

## Monitoring & Analytics

### Health Checks

The application includes health check endpoints:

- `GET /health` - Application health status
- `GET /api/chat/stats` - User conversation analytics

### Logging

Structured logging with the following levels:
- INFO: Normal operations
- WARNING: Potential issues
- ERROR: Failures requiring attention

### Metrics

Track these key metrics:
- Chatbot response time
- Intent classification accuracy
- User satisfaction scores
- API error rates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit a pull request

### AI Development Guidelines

- Always include fallback responses
- Test AI features with API failures
- Document intent classification examples
- Include privacy considerations
- Test edge cases and error handling

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please contact:
- Email: support@drivingschool.com
- Documentation: [Wiki](https://github.com/yourusername/driving-lesson-system/wiki)
- Issues: [GitHub Issues](https://github.com/yourusername/driving-lesson-system/issues)
