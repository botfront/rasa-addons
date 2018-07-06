import logging
from flask_socketio import SocketIO, emit
from flask import Blueprint, send_from_directory, request, jsonify
from rasa_core.channels import HttpInputComponent, OutputChannel, HttpInputChannel, UserMessage

logger = logging.getLogger(__name__)


class WebchatBot(OutputChannel):

    def __init__(self):
        self.custom_data = {}

    def send(self, recipient_id, message):
        # type: (Text, Any) -> None
        """Sends a message to the recipient."""
        emit(message, room=recipient_id)

    def send_text_message(self, recipient_id, message):
        # type: (Text, Text) -> None
        """Send a message through this channel."""

        logger.info("Sending message: " + message)
        emit('bot_uttered', {"text": message}, room=recipient_id)

    def send_image_url(self, recipient_id, image_url):
        # type: (Text, Text) -> None
        """Sends an image. Default will just post the url as a string."""
        message = {"attachment": {
            "type": "image",
            "payload": {
                # "title": "generic", commented because it's supported, but standard rasa dispatcher only sends the url for now
                "src": image_url
            }}}
        emit('bot_uttered', message, room=recipient_id)

    def send_text_with_buttons(self, recipient_id, text, buttons, **kwargs):
        # type: (Text, Text, List[Dict[Text, Any]], **Any) -> None
        """Sends buttons to the output."""

        message = {
            "text": text,
            "quick_replies": []
        }

        for button in buttons:
            message["quick_replies"].append({
                    "content_type": "text",
                    "title": button['title'],
                    "payload": button['payload']
                })

        emit('bot_uttered', message, room=recipient_id)

    def send_custom_message(self, recipient_id, elements):
        # type: (Text, List[Dict[Text, Any]]) -> None
        """Sends elements to the output."""

        message = {"attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": elements[0]
            }}}

        emit('bot_uttered', message, room=recipient_id)


class WebChatInput(HttpInputComponent):
    """Webchat input channel implementation. Based on the HTTPInputChannel."""

    def __init__(self, static_assets_path=None, index='index.html'):
        # type: (Text, Text) -> None

        self.static_assets_path = static_assets_path
        self.index = index

    def blueprint(self, on_new_message):

        web_chat_webhook = Blueprint('web_chat_webhook', __name__)

        @web_chat_webhook.route('/health')
        def health():
            return jsonify({"status": "ok"})

        if self.static_assets_path is not None and self.index is not None:
            @web_chat_webhook.route('/<path:path>')
            def send_path(path):
                return send_from_directory(self.static_assets_path, path)

            @web_chat_webhook.route("/", methods=['GET'])
            def bot():
                return send_from_directory(self.static_assets_path, self.index)

        return web_chat_webhook


class SocketInputChannel(HttpInputChannel):

    def _record_messages(self, on_message):
        # type: (Callable[[UserMessage], None]) -> None
        from flask import Flask
        from flask_cors import CORS

        app = Flask(__name__)
        CORS(app)
        app.config['SECRET_KEY'] = 'secret!'

        for component in self.listener_components:
            if self._has_root_prefix():
                app.register_blueprint(component.blueprint(on_message))
            else:
                app.register_blueprint(component.blueprint(on_message),
                                       url_prefix=self.url_prefix)

        socketio = SocketIO(app)

        @socketio.on('connect')
        def on_connect():
            pass

        @socketio.on('user_uttered')
        def handle_message(message):
            output_channel = WebchatBot()
            output_channel.custom_data = message['customData']
            on_message(UserMessage(message['message'], output_channel, request.sid))

        cors = CORS(app, resources={r"*": {"origins": "*"}})  # TODO change that

        socketio.run(app, port=self.http_port, host='0.0.0.0')
