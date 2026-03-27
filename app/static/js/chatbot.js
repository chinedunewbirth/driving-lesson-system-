// Enhanced Chatbot functionality for DriveSmart with AI action capabilities
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');
    const typingIndicator = document.getElementById('typing-indicator');

    if (!chatForm) return;

    let conversationStats = { total_messages: 0, intents: {} };

    function getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }

    // Handle form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const message = messageInput.value.trim();
        if (!message) return;

        addMessage(message, 'user');

        messageInput.value = '';
        setLoading(true);
        showTypingIndicator(true);

        sendMessage(message);
    });

    // Send message to API
    function sendMessage(message) {
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => {
            if (!response.ok) throw new Error('HTTP error ' + response.status);
            return response.json();
        })
        .then(data => {
            hideTypingIndicator();

            if (data.error) {
                addMessage(data.response, 'bot', 'error');
            } else {
                addMessage(data.response, 'bot', 'success', data.intent, data.confidence);

                // Render action result cards if present
                if (data.action_result) {
                    renderActionResult(data.action_result);
                }

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

    // ── Action Result Renderer ──────────────────────────────────────
    function renderActionResult(result) {
        const wrapper = document.createElement('div');
        wrapper.className = 'action-result mb-3 animate__animated animate__fadeInUp';

        const card = document.createElement('div');
        card.className = 'card border-0 shadow-sm me-auto';
        card.style.maxWidth = '90%';

        const body = document.createElement('div');
        body.className = 'card-body p-3';

        switch (result.type) {
            case 'lesson_list':
            case 'reschedule_list':
            case 'cancel_list':
                body.innerHTML = buildLessonList(result);
                break;
            case 'instructor_list':
                body.innerHTML = buildInstructorList(result);
                break;
            case 'refund_list':
                body.innerHTML = buildRefundList(result);
                break;
            case 'book_form':
                body.innerHTML = buildBookForm(result);
                break;
            case 'slot_list':
                body.innerHTML = buildSlotList(result);
                break;
            case 'need_info':
                body.innerHTML = '<p class="mb-0 text-muted"><i class="fas fa-info-circle me-1"></i>' + escapeHtml(result.message) + '</p>';
                break;
            case 'error':
                body.innerHTML = '<p class="mb-0 text-danger"><i class="fas fa-exclamation-triangle me-1"></i>' + escapeHtml(result.message) + '</p>';
                break;
            default:
                return; // Unknown type, skip
        }

        card.appendChild(body);
        wrapper.appendChild(card);
        chatMessages.appendChild(wrapper);
        scrollToBottom();

        // Attach event listeners to action buttons
        attachActionListeners(wrapper);
    }

    // ── Card Builders ───────────────────────────────────────────────

    function buildLessonList(result) {
        const isReschedule = result.type === 'reschedule_list';
        const isCancel = result.type === 'cancel_list';

        let html = '<h6 class="mb-2"><i class="fas fa-calendar-alt me-1 text-primary"></i>' + escapeHtml(result.title) + '</h6>';

        if (!result.items || result.items.length === 0) {
            return html + '<p class="text-muted mb-0">' + escapeHtml(result.empty_message) + '</p>';
        }

        result.items.forEach(function(item) {
            html += '<div class="border rounded p-2 mb-2 d-flex justify-content-between align-items-center" style="background:var(--ds-surface-alt);">';
            html += '<div>';
            html += '<strong>' + escapeHtml(item.instructor_name || item.student_name || '') + '</strong><br>';
            html += '<small class="text-muted">' + escapeHtml(item.date || '') + ' at ' + escapeHtml(item.time || '') + '</small>';
            if (item.duration) html += '<small class="text-muted ms-2">(' + item.duration + 'h)</small>';
            html += '</div><div>';

            if (isReschedule) {
                html += '<button class="btn btn-sm btn-outline-warning action-reschedule-btn" data-lesson-id="' + item.id + '"><i class="fas fa-calendar-plus me-1"></i>Reschedule</button>';
            } else if (isCancel) {
                html += '<button class="btn btn-sm btn-outline-danger action-cancel-btn" data-lesson-id="' + item.id + '"><i class="fas fa-times me-1"></i>Cancel</button>';
            }

            html += '</div></div>';
        });

        return html;
    }

    function buildInstructorList(result) {
        let html = '<h6 class="mb-2"><i class="fas fa-chalkboard-teacher me-1 text-primary"></i>' + escapeHtml(result.title) + '</h6>';

        if (!result.items || result.items.length === 0) {
            return html + '<p class="text-muted mb-0">' + escapeHtml(result.empty_message) + '</p>';
        }

        result.items.forEach(function(item) {
            html += '<div class="border rounded p-2 mb-2" style="background:var(--ds-surface-alt);">';
            html += '<div class="d-flex justify-content-between align-items-start">';
            html += '<div>';
            html += '<strong>' + escapeHtml(item.name) + '</strong>';
            if (item.distance_km !== null && item.distance_km !== undefined) {
                html += ' <span class="badge bg-success ms-1">' + item.distance_km + ' km</span>';
            }
            html += '<br>';
            if (item.hourly_rate) html += '<small class="text-success fw-bold">&pound;' + item.hourly_rate + '/hr</small> ';
            if (item.address) html += '<small class="text-muted"><i class="fas fa-map-marker-alt me-1"></i>' + escapeHtml(item.address) + '</small>';
            if (item.bio) html += '<br><small class="text-muted">' + escapeHtml(item.bio) + '</small>';
            html += '</div>';
            html += '<button class="btn btn-sm btn-primary action-book-instructor-btn" data-instructor-id="' + item.id + '" data-instructor-name="' + escapeHtml(item.name) + '"><i class="fas fa-plus me-1"></i>Book</button>';
            html += '</div></div>';
        });

        return html;
    }

    function buildRefundList(result) {
        let html = '<h6 class="mb-2"><i class="fas fa-money-bill-wave me-1 text-primary"></i>' + escapeHtml(result.title) + '</h6>';

        if (!result.items || result.items.length === 0) {
            return html + '<p class="text-muted mb-0">' + escapeHtml(result.empty_message) + '</p>';
        }

        result.items.forEach(function(item) {
            html += '<div class="border rounded p-2 mb-2 d-flex justify-content-between align-items-center" style="background:var(--ds-surface-alt);">';
            html += '<div>';
            html += '<strong>&pound;' + (item.amount || '0') + '</strong>';
            html += '<br><small class="text-muted">Paid ' + escapeHtml(item.date || '') + '</small>';
            if (item.instructor) html += ' <small class="text-muted">to ' + escapeHtml(item.instructor) + '</small>';
            html += '</div>';
            html += '<button class="btn btn-sm btn-outline-danger action-refund-btn" data-payment-id="' + item.id + '"><i class="fas fa-undo me-1"></i>Refund</button>';
            html += '</div>';
        });

        return html;
    }

    function buildBookForm(result) {
        var prefill = result.prefill || {};
        var instructors = result.instructors || [];

        var html = '<h6 class="mb-2"><i class="fas fa-calendar-plus me-1 text-primary"></i>' + escapeHtml(result.title) + '</h6>';
        html += '<div id="book-form-container">';

        // Instructor select
        html += '<div class="mb-2"><label class="form-label small mb-1">Instructor</label>';
        html += '<select class="form-select form-select-sm" id="action-book-instructor">';
        html += '<option value="">Select an instructor</option>';
        instructors.forEach(function(inst) {
            var sel = (prefill.instructor_id && prefill.instructor_id == inst.id) ? ' selected' : '';
            var rate = inst.hourly_rate ? ' (\u00a3' + inst.hourly_rate + '/hr)' : '';
            html += '<option value="' + inst.id + '"' + sel + '>' + escapeHtml(inst.name) + rate + '</option>';
        });
        html += '</select></div>';

        // Date
        var today = new Date().toISOString().split('T')[0];
        html += '<div class="mb-2"><label class="form-label small mb-1">Date</label>';
        html += '<input type="date" class="form-control form-control-sm" id="action-book-date" min="' + today + '" value="' + (prefill.date || '') + '"></div>';

        // Time
        html += '<div class="mb-2"><label class="form-label small mb-1">Time</label>';
        html += '<input type="time" class="form-control form-control-sm" id="action-book-time" value="' + (prefill.time || '') + '"></div>';

        // Duration
        html += '<div class="mb-2"><label class="form-label small mb-1">Duration (hours)</label>';
        html += '<select class="form-select form-select-sm" id="action-book-duration">';
        [1, 1.5, 2].forEach(function(d) {
            var sel = (prefill.duration && prefill.duration == d) ? ' selected' : '';
            html += '<option value="' + d + '"' + sel + '>' + d + ' hour' + (d > 1 ? 's' : '') + '</option>';
        });
        html += '</select></div>';

        // Pickup (optional)
        html += '<div class="mb-2"><label class="form-label small mb-1">Pickup address (optional)</label>';
        html += '<input type="text" class="form-control form-control-sm" id="action-book-pickup" placeholder="e.g. 10 High Street"></div>';

        html += '<button class="btn btn-sm btn-primary w-100 action-confirm-book-btn"><i class="fas fa-check me-1"></i>Confirm Booking</button>';
        html += '</div>';

        return html;
    }

    function buildSlotList(result) {
        var html = '<h6 class="mb-2"><i class="fas fa-clock me-1 text-primary"></i>' + escapeHtml(result.title) + '</h6>';

        if (!result.slots || result.slots.length === 0) {
            return html + '<p class="text-muted mb-0">' + escapeHtml(result.empty_message) + '</p>';
        }

        html += '<div class="d-flex flex-wrap gap-1">';
        result.slots.forEach(function(slot) {
            html += '<button class="btn btn-sm btn-outline-primary action-pick-slot-btn" '
                + 'data-instructor-id="' + result.instructor_id + '" '
                + 'data-instructor-name="' + escapeHtml(result.instructor_name) + '" '
                + 'data-date="' + result.date + '" '
                + 'data-time="' + slot + '">'
                + slot + '</button>';
        });
        html += '</div>';

        return html;
    }

    // ── Action Listeners ────────────────────────────────────────────

    function attachActionListeners(container) {
        // Book instructor button (from instructor list)
        container.querySelectorAll('.action-book-instructor-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var instId = this.dataset.instructorId;
                var instName = this.dataset.instructorName;
                messageInput.value = 'Book a lesson with ' + instName;
                chatForm.dispatchEvent(new Event('submit'));
            });
        });

        // Pick time slot → open inline booking
        container.querySelectorAll('.action-pick-slot-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var instId = this.dataset.instructorId;
                var instName = this.dataset.instructorName;
                var date = this.dataset.date;
                var time = this.dataset.time;
                messageInput.value = 'Book ' + instName + ' on ' + date + ' at ' + time;
                chatForm.dispatchEvent(new Event('submit'));
            });
        });

        // Confirm booking from form
        container.querySelectorAll('.action-confirm-book-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var instructor = document.getElementById('action-book-instructor');
                var dateEl = document.getElementById('action-book-date');
                var timeEl = document.getElementById('action-book-time');
                var dur = document.getElementById('action-book-duration');
                var pickup = document.getElementById('action-book-pickup');

                if (!instructor.value || !dateEl.value || !timeEl.value) {
                    addMessage('Please fill in instructor, date, and time to book.', 'bot', 'error');
                    return;
                }

                this.disabled = true;
                this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Booking...';

                executeAction('confirm_book', {
                    instructor_id: parseInt(instructor.value),
                    date: dateEl.value,
                    time: timeEl.value,
                    duration: parseFloat(dur.value),
                    pickup_address: pickup.value || null,
                });
            });
        });

        // Reschedule
        container.querySelectorAll('.action-reschedule-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var lessonId = this.dataset.lessonId;
                showReschedulePrompt(lessonId, this);
            });
        });

        // Cancel
        container.querySelectorAll('.action-cancel-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var lessonId = this.dataset.lessonId;
                if (confirm('Are you sure you want to cancel this lesson?')) {
                    this.disabled = true;
                    this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>';
                    executeAction('confirm_cancel', { lesson_id: parseInt(lessonId) });
                }
            });
        });

        // Refund
        container.querySelectorAll('.action-refund-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var paymentId = this.dataset.paymentId;
                if (confirm('Request a refund for this payment?')) {
                    this.disabled = true;
                    this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>';
                    executeAction('confirm_refund', { payment_id: parseInt(paymentId), reason: 'Requested via AI assistant' });
                }
            });
        });
    }

    function showReschedulePrompt(lessonId, btn) {
        // Create inline reschedule form next to the button
        var parent = btn.closest('.border');
        var existing = parent.querySelector('.reschedule-form');
        if (existing) { existing.remove(); return; }

        var today = new Date().toISOString().split('T')[0];
        var form = document.createElement('div');
        form.className = 'reschedule-form mt-2 p-2 border-top';
        form.innerHTML = '<div class="row g-1">'
            + '<div class="col-5"><input type="date" class="form-control form-control-sm resc-date" min="' + today + '"></div>'
            + '<div class="col-4"><input type="time" class="form-control form-control-sm resc-time"></div>'
            + '<div class="col-3"><button class="btn btn-sm btn-warning w-100 resc-confirm-btn">Go</button></div>'
            + '</div>';
        parent.appendChild(form);

        form.querySelector('.resc-confirm-btn').addEventListener('click', function() {
            var d = form.querySelector('.resc-date').value;
            var t = form.querySelector('.resc-time').value;
            if (!d || !t) { addMessage('Please pick a new date and time.', 'bot', 'error'); return; }
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            executeAction('confirm_reschedule', {
                lesson_id: parseInt(lessonId),
                new_date: d,
                new_time: t,
                reason: 'Rescheduled via AI assistant',
            });
        });
    }

    // ── Execute Confirmed Action ────────────────────────────────────

    function executeAction(actionType, params) {
        showTypingIndicator(true);

        var payload = Object.assign({ action: actionType }, params);

        fetch('/api/chat/action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(payload)
        })
        .then(function(response) { return response.json(); })
        .then(function(data) {
            hideTypingIndicator();
            if (data.success) {
                addMessage(data.message || 'Done!', 'bot', 'success');
            } else {
                addMessage(data.message || data.error || 'Action failed.', 'bot', 'error');
            }
        })
        .catch(function(err) {
            hideTypingIndicator();
            console.error('Action error:', err);
            addMessage('Something went wrong. Please try again.', 'bot', 'error');
        });
    }

    // ── Core Chat Functions ─────────────────────────────────────────

    function addMessage(text, sender, type, intent, confidence) {
        type = type || 'normal';
        var messageDiv = document.createElement('div');
        messageDiv.className = 'message ' + sender + '-message mb-3 animate__animated animate__fadeInUp';

        var messageCard = document.createElement('div');
        messageCard.className = 'card border-0 shadow-sm';

        var cardBody = document.createElement('div');
        cardBody.className = 'card-body p-3';

        if (sender === 'user') {
            messageCard.className += ' bg-primary text-white ms-auto';
            messageCard.style.maxWidth = '80%';
            cardBody.innerHTML = '<div class="d-flex align-items-center mb-1">'
                + '<strong class="me-2"><i class="fas fa-user me-1"></i>You:</strong>'
                + '<small class="text-primary-emphasis">' + new Date().toLocaleTimeString() + '</small>'
                + '</div>'
                + '<p class="mb-0">' + escapeHtml(text) + '</p>';
        } else {
            messageCard.className += ' bg-light me-auto';
            messageCard.style.maxWidth = '80%';
            var intentBadge = '';
            if (intent && intent !== 'unknown') {
                var pct = Math.round((confidence || 0) * 100);
                intentBadge = '<span class="badge bg-info ms-2">' + intent + ' (' + pct + '%)</span>';
            }
            cardBody.innerHTML = '<div class="d-flex align-items-center mb-1">'
                + '<strong class="me-2"><i class="fas fa-robot me-1"></i>AI Assistant:</strong>'
                + '<small class="text-muted">' + new Date().toLocaleTimeString() + '</small>'
                + intentBadge
                + '</div>'
                + '<p class="mb-0">' + escapeHtml(text) + '</p>';
        }

        if (type === 'error') {
            messageCard.className += ' border-danger';
            cardBody.className += ' text-danger';
        }

        messageCard.appendChild(cardBody);
        messageDiv.appendChild(messageCard);
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function showTypingIndicator(show) {
        if (!typingIndicator) return;
        if (show) {
            typingIndicator.classList.remove('d-none');
            typingIndicator.innerHTML = '<div class="d-flex align-items-center">'
                + '<div class="spinner-border spinner-border-sm me-2" role="status"><span class="visually-hidden">Loading...</span></div>'
                + '<small class="text-muted">AI Assistant is thinking...</small></div>';
        } else {
            typingIndicator.classList.add('d-none');
        }
    }

    function hideTypingIndicator() { showTypingIndicator(false); }

    function setLoading(loading) {
        if (loading) {
            sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
            sendBtn.disabled = true;
            messageInput.disabled = true;
        } else {
            sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
            sendBtn.disabled = false;
            messageInput.disabled = false;
        }
    }

    function updateConversationStats(intent) {
        conversationStats.total_messages = (conversationStats.total_messages || 0) + 1;
        conversationStats.intents = conversationStats.intents || {};
        conversationStats.intents[intent] = (conversationStats.intents[intent] || 0) + 1;

        var statsElement = document.getElementById('conversation-stats');
        if (statsElement) {
            var top = Object.entries(conversationStats.intents)
                .sort(function(a, b) { return b[1] - a[1]; })
                .slice(0, 3)
                .map(function(e) { return e[0] + ' (' + e[1] + ')'; })
                .join(', ');
            statsElement.textContent = 'Messages: ' + conversationStats.total_messages + ' | ' + (top || 'None');
        }
    }

    function scrollToBottom() {
        var container = document.getElementById('chat-container');
        container.scrollTop = container.scrollHeight;
    }

    // Handle Enter key
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    messageInput.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            var start = this.selectionStart;
            var end = this.selectionEnd;
            this.value = this.value.substring(0, start) + '\n' + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 1;
        }
    });

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    messageInput.focus();

    if (typeof currentUser !== 'undefined' && currentUser.is_authenticated) {
        loadConversationStats();
    }

    function loadConversationStats() {
        fetch('/api/chat/stats')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data.error) {
                conversationStats = data;
                var statsElement = document.getElementById('conversation-stats');
                if (statsElement && data.intents) {
                    var top = Object.entries(data.intents)
                        .sort(function(a, b) { return b[1] - a[1]; })
                        .slice(0, 3)
                        .map(function(e) { return e[0] + ' (' + e[1] + ')'; })
                        .join(', ');
                    statsElement.textContent = 'Messages: ' + (data.total_messages || 0) + ' | ' + (top || 'None yet');
                }
            }
        })
        .catch(function(err) { console.error('Error loading stats:', err); });
    }
});