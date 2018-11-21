import logging
from flask_socketio import SocketIO, emit
from flask import Blueprint, send_from_directory, request, jsonify
from rasa_core.channels import InputChannel, OutputChannel, HttpInputChannel, UserMessage

logger = logging.getLogger(__name__)


class SocketOutputChatBot(SocketIOOutput):
    @classmethod
    def name(cls):
        return 'webchat'


class SocketInputChatBot(SocketIOInput):
    def __init__(self, static_assets_path=None, index='index.html', socketio_path='/socket.io'):
        # type: (Text, Text) -> None
        
        self.static_assets_path = static_assets_path
        self.index = index
        
        super(SocketInputChatBot, self).__init__(socketio_path=socketio_path)

    @classmethod
    def name(cls):
        return 'webchat'

    def blueprint(self, on_new_message):
        sio = socketio.Server()
        name = SocketInputChatBot.name()
        socketio_webhook = SocketBlueprint(sio, self.socketio_path, name, __name__,
                                           url_prefix=SocketInputChatBot.name(),
                                           static_folder=self.static_assets_path,
                                           static_url_path='/{}'.format(name))

        # send view if static_assets are present
        if self.static_assets_path is not None and self.index is not None:
            @socketio_webhook.route('/<path:path>')
            def send_path(path):
                return send_from_directory(self.static_assets_path, path)

            @socketio_webhook.route('/', methods=['GET'])
            def bot():
                return send_from_directory(self.static_assets_path, self.index)

        # socket specific endpoints and event handler
        @socketio_webhook.route('/health', methods=['GET'])
        def health():
            return jsonify({'status': 'ok'})

        @sio.on('connect', namespace=self.namespace)
        def connect(sid, environ):
            logger.debug('User {} connected to socketio endpoint.'.format(sid))

        @sio.on('disconnect', namespace=self.namespace)
        def disconnect(sid):
            logger.debug('User {} disconnected from socketio endpoint.'.format(sid))

        @sio.on(self.user_message_evt, namespace=self.namespace)
        def handle_message(sid, data):
            output_channel = SocketOutputChatBot(sio, self.bot_message_evt)
            message = UserMessage(data['message'], output_channel, sid, input_channel=self.name())
            on_new_message(message)

        return socketio_webhook


''' Can be invoked as follows in RASA Core 0.12.x


        static_asset_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
        webchat = SocketInputChatBot(static_assets_path=static_asset_path)

        interpreter = RasaNLUInterpreter('models/nlu/default/current')
        agent = Agent.load(dir_model_core, interpreter=interpreter)
        agent.handle_channels([webchat], 5000, serve_forever=True, route='/')
'''
