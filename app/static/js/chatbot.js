// Chatbot functionality for DriveSmart
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');

    if (!chatForm) return;

    // Handle form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, 'user');

        // Clear input and disable form temporarily
        messageInput.value = '';
        setLoading(true);

        // Send message to server
        fetch(chatForm.action, {
            method: 'POST',
            body: new FormData(chatForm)
        })
        .then(response => response.json())
        .then(data => {
            // Add bot response to chat
            addMessage(data.response, 'bot');
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        })
        .finally(() => {
            setLoading(false);
            messageInput.focus();
        });
    });

    // Add message to chat
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message mb-2`;

        const messageP = document.createElement('p');
        messageP.className = 'mb-0 p-2 rounded';

        if (sender === 'user') {
            messageP.className += ' bg-primary text-white ms-auto';
            messageP.style.maxWidth = '80%';
            messageP.innerHTML = `<strong>You:</strong> ${text}`;
        } else {
            messageP.className += ' bg-light me-auto';
            messageP.style.maxWidth = '80%';
            messageP.innerHTML = `<strong><i class="fas fa-robot me-1"></i>Bot:</strong> ${text}`;
        }

        messageDiv.appendChild(messageP);
        chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        scrollToBottom();
    }

    // Set loading state
    function setLoading(loading) {
        if (loading) {
            sendBtn.innerHTML = '<span class="loading me-1"></span>Sending...';
            sendBtn.disabled = true;
            messageInput.disabled = true;
        } else {
            sendBtn.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Send';
            sendBtn.disabled = false;
            messageInput.disabled = false;
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

    // Focus input on page load
    messageInput.focus();
});