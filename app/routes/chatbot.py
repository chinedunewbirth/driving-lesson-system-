from flask import Blueprint, request, jsonify, render_template
from app.ai_chatbot import ChatBot
from app.forms import ChatbotForm

bp = Blueprint('chatbot', __name__)
Chatbot = ChatBot()

@bp.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    form = ChatbotForm()
    if form.validate_on_submit():
        user_input = form.message.data
        response = Chatbot.get_response(user_input)
        return jsonify({'response': response})
    return render_template('chatbot.html', form=form)
