// Enhanced Chatbot functionality for DriveSmart with AI capabilities
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');
    const typingIndicator = document.getElementById('typing-indicator');

    if (!chatForm) return;

    let conversationStats = { total_messages: 0, intents: {} };

    // Handle form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, 'user');

        // Clear input and show typing indicator
        messageInput.value = '';
        setLoading(true);
        showTypingIndicator(true);

        // Send message to API
        sendMessage(message);
    });

    // Send message to API
    function sendMessage(message) {
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            hideTypingIndicator();

            if (data.error) {
                addMessage(data.response, 'bot', 'error');
            } else {
                // Add bot response with intent information
                addMessage(data.response, 'bot', 'success', data.intent, data.confidence);

                // Update conversation stats if available
                if (data.intent) {
                    updateConversationStats(data.intent);
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            hideTypingIndicator();
            addMessage('Sorry, I encountered an error. Please try again or contact support.', 'bot', 'error');
        })
        .finally(() => {
            setLoading(false);
            messageInput.focus();
        });
    }

    // Add message to chat with enhanced features
    function addMessage(text, sender, type = 'normal', intent = null, confidence = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message mb-3 animate__animated animate__fadeInUp`;

        const messageCard = document.createElement('div');
        messageCard.className = 'card border-0 shadow-sm';

        const cardBody = document.createElement('div');
        cardBody.className = 'card-body p-3';

        if (sender === 'user') {
            messageCard.className += ' bg-primary text-white ms-auto';
            messageCard.style.maxWidth = '80%';
            cardBody.innerHTML = `
                <div class="d-flex align-items-center mb-1">
                    <strong class="me-2"><i class="fas fa-user me-1"></i>You:</strong>
                    <small class="text-primary-emphasis">${new Date().toLocaleTimeString()}</small>
                </div>
                <p class="mb-0">${escapeHtml(text)}</p>
            `;
        } else {
            messageCard.className += ' bg-light me-auto';
            messageCard.style.maxWidth = '80%';
            let intentBadge = '';
            if (intent && intent !== 'unknown') {
                const confidencePercent = Math.round(confidence * 100);
                intentBadge = `<span class="badge bg-info ms-2">${intent} (${confidencePercent}%)</span>`;
            }

            cardBody.innerHTML = `
                <div class="d-flex align-items-center mb-1">
                    <strong class="me-2"><i class="fas fa-robot me-1"></i>AI Assistant:</strong>
                    <small class="text-muted">${new Date().toLocaleTimeString()}</small>
                    ${intentBadge}
                </div>
                <p class="mb-0">${escapeHtml(text)}</p>
            `;
        }

        // Add error styling
        if (type === 'error') {
            messageCard.className += ' border-danger';
            cardBody.className += ' text-danger';
        }

        messageCard.appendChild(cardBody);
        messageDiv.appendChild(messageCard);
        chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        scrollToBottom();
    }

    // Show/hide typing indicator
    function showTypingIndicator(show) {
        if (!typingIndicator) return;

        if (show) {
            typingIndicator.classList.remove('d-none');
            typingIndicator.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm me-2" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <small class="text-muted">AI Assistant is thinking...</small>
                </div>
            `;
        } else {
            typingIndicator.classList.add('d-none');
        }
    }

    function hideTypingIndicator() {
        showTypingIndicator(false);
    }

    // Set loading state
    function setLoading(loading) {
        if (loading) {
            sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Sending...';
            sendBtn.disabled = true;
            messageInput.disabled = true;
        } else {
            sendBtn.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Send';
            sendBtn.disabled = false;
            messageInput.disabled = false;
        }
    }

    // Update conversation statistics
    function updateConversationStats(intent) {
        conversationStats.total_messages = (conversationStats.total_messages || 0) + 1;
        conversationStats.intents = conversationStats.intents || {};
        conversationStats.intents[intent] = (conversationStats.intents[intent] || 0) + 1;

        // Update stats display if element exists
        const statsElement = document.getElementById('conversation-stats');
        if (statsElement) {
            statsElement.innerHTML = `
                <small class="text-muted">
                    Messages: ${conversationStats.total_messages} |
                    Top topics: ${Object.entries(conversationStats.intents)
                        .sort(([,a],[,b]) => b-a)
                        .slice(0, 3)
                        .map(([intent, count]) => `${intent} (${count})`)
                        .join(', ')}
                </small>
            `;
        }
    }

    // Scroll chat to bottom
    function scrollToBottom() {
        const container = document.getElementById('chat-container');
        container.scrollTop = container.scrollHeight;
    }

    // Handle Enter key
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Handle keyboard shortcuts
    messageInput.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + Enter for new line
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + '\n' + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 1;
        }
    });

    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Focus input on page load
    messageInput.focus();

    // Load conversation stats on page load
    if (typeof currentUser !== 'undefined' && currentUser.is_authenticated) {
        loadConversationStats();
    }

    function loadConversationStats() {
        fetch('/api/chat/stats')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                conversationStats = data;
                // Update stats display with loaded data
                const statsElement = document.getElementById('conversation-stats');
                if (statsElement && data.intents) {
                    statsElement.innerHTML = `
                        <small class="text-muted">
                            Messages: ${data.total_messages || 0} |
                            Top topics: ${Object.entries(data.intents)
                                .sort(([,a],[,b]) => b-a)
                                .slice(0, 3)
                                .map(([intent, count]) => `${intent} (${count})`)
                                .join(', ') || 'None yet'}
                        </small>
                    `;
                }
            }
        })
        .catch(error => console.error('Error loading stats:', error));
    }
});