"""
socket_events.py — handles real-time chat messages using WebSockets.
"""

from flask_socketio import emit
from flask_app import socketio
from flask_app.utils.llm import handle_ai_chat_request

import flask_app.routes as routes


@socketio.on('send_message')
def handle_message(data):
    """
    Handle a chat message from the browser.
    """

    user_message = data.get('message', '').strip()

    if not user_message:
        return

    # Get the database instance created by create_app()
    db = routes.db

    if db is None:
        emit(
            'receive_message',
            {
                'response': '⚠️ Database is not initialized.'
            }
        )
        return

    try:
        # Route every chat request through the Orchestrator.
        ai_response = handle_ai_chat_request(
            db,
            "Orchestrator",
            user_message
        )

    except Exception as error:
        print(f"AI error: {error}")

        ai_response = (
            f"⚠️ Could not process the request: {error}"
        )

    emit(
        'receive_message',
        {
            'response': ai_response
        }
    )