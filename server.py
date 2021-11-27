
# 
# Copyright (c) 2020, 2021, John Grundback
# All rights reserved.
# 

import os
import logging

import simplejson as json

from functools import partial

import asyncio
import threading

from flask import Flask
from flask_restful import Api
from flask_cors import CORS, cross_origin
from flask_swagger import swagger
from flask import Response, request
from flask.views import View

from graphql.type.schema import GraphQLSchema
from graphql_server import (
    HttpQueryError, 
    default_format_error, 
    encode_execution_results, 
    json_encode, 
    load_json_body, 
    run_http_query
)
from graphql.backend import GraphQLCoreBackend

from flask_graphql import GraphQLView
from flask_graphql.render_graphiql import render_graphiql

from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from flask_socketio import SocketIO
from flask_socketio import send, emit
from flask_sockets import Sockets
from graphql_ws.gevent import  GeventSubscriptionServer

# 
# 
# 

app = Flask(__name__)
cors = CORS(app)

app.config["DEBUG"] = True
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = 'secret!'

api = Api(app)
# socketio = SocketIO(app)
# socketio = SocketIO(app, logger=True, engineio_logger=True, debug=True)
socketio = SocketIO(app, cors_allowed_origins="*")

sockets = Sockets(app)
app.app_protocol = lambda environ_path_info: 'graphql-ws'

listen_addr = os.environ.get("LISTEN_ADDR", "0.0.0.0")
listen_port = os.environ.get("LISTEN_PORT", "5000")

# 
# 
# 

from graphql_tools import build_executable_schema

source_schema = """

type User {
    username: String
    userId: String
}

type Message {
    content: String
    senderId: String
    recipientId: String
}

type createUserResult {
    user: User
    success: Boolean!
    errors: [String]
}

type createMessageResult {
    message: Message
    success: Boolean!
    errors: [String]
}

type messagesResult {
    messages: [Message]
    success: Boolean!
    errors: [String]
}

type Query {
    hello: String!
    messages(userId: String!): messagesResult
    userId(username: String!): String
}

type Mutation {
    createUser(username: String!): createUserResult
    createMessage(senderId: String, recipientId: String, content: String): createMessageResult
}

type Subscription {
    messages(userId: String): Message
}

schema {
  query: Query
  mutation: Mutation
  subscription: Subscription
}

"""

def subscription_messages_resolver(value, info, **args):
    print("subscription_messages_resolver")

resolvers = {
  "Subscription": {
      "messages": subscription_messages_resolver
  }
}

my_schema = build_executable_schema(source_schema, resolvers)

# 
# 
# 


@socketio.on('connect', namespace='/gfs1')
def gfs1_connect():
    emit('message', {'data': 'Connected'})

@socketio.on('disconnect', namespace='/gfs1')
def gfs1_disconnect():
    pass

@socketio.on('message', namespace='/gfs1')
def handle_message(message):
    emit("message", "message response")



@sockets.route('/subscriptions')
def subscriptions_handler(ws):
    subscription_server = GeventSubscriptionServer(
        my_schema
    )
    subscription_server.handle(ws)
    return []

@sockets.route('/graphql/subscriptions')
def subscriptions_handler2(ws):
    subscription_server = GeventSubscriptionServer(
        my_schema
    )
    subscription_server.handle(ws)
    return []




class CustomBackend(GraphQLCoreBackend):
    def __init__(self, executor=None):
        super().__init__(executor)
        self.execute_params['allow_subscriptions'] = True



class GQLView(View):

    schema = None

    methods = ['GET', 'POST', 'PUT', 'DELETE']

    def __init__(self, **kwargs):
        super(GQLView, self).__init__()
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def context(self):
        return request

    def schema(self):
        return self.schema

    def graphiql(self, params, result):
        return render_graphiql(
            params=params,
            result=result
        )

    format_error = staticmethod(default_format_error)
    encode = staticmethod(json_encode)

    def dispatch_request(self):

        try:

            show_graphiql = request.method.lower() == 'get' and self.is_graphiql()

            data = self.parse_body()

            # opts = {}

            opts = {
                "MIDDLEWARE": [], 
                "allow_subscriptions": True
            }

            execution_results, all_params = run_http_query(
                self.schema,
                request.method.lower(),
                data,
                query_data=request.args,
                catch=show_graphiql,
                context=self.context(),
                middleware=[],
                # backend=
                backend=CustomBackend(),
                **opts
            )

            result, status_code = encode_execution_results(
                execution_results,
                is_batch=isinstance(data, list),
                format_error=self.format_error,
                encode=partial(self.encode, pretty=True)
            )

            if show_graphiql:
                return self.graphiql(
                    params=all_params[0],
                    result=result
                )

            return Response(
                result,
                status=status_code,
                content_type='application/json'
            )

        except HttpQueryError as e:
            return Response(
                self.encode({
                    'errors': [self.format_error(e)]
                }),
                status=e.status_code,
                headers=e.headers,
                content_type='application/json'
            )

    def parse_body(self):
        if request.mimetype == 'application/graphql':
            return {
                'query': request.data.decode('utf8')
            }

        elif request.mimetype == 'application/json':
            return load_json_body(
                request.data.decode('utf8')
            )

        return {}

    def is_graphiql(self):
        return self.is_html()

    def is_html(self):
        best = request.accept_mimetypes \
            .best_match(['application/json', 'text/html'])
        return best == 'text/html' and \
            request.accept_mimetypes[best] > \
            request.accept_mimetypes['application/json']





view_func = GQLView.as_view(
    'graphql',
    schema=my_schema
)
app.add_url_rule(
    '/graphql', 
    view_func=view_func
)

class GraphQLSchema(View):

    def dispatch_request(self):
        schema=my_schema
        return str( schema )

view_func2 = GraphQLSchema.as_view(
    'graphql2'
)
app.add_url_rule(
    '/graphql/schema', 
    view_func=view_func2
)

print(str(listen_addr))
print(int(listen_port))

# server = pywsgi.WSGIServer(('0.0.0.0', 5000), app, handler_class=WebSocketHandler)
server = pywsgi.WSGIServer((str(listen_addr), int(listen_port)), app, handler_class=WebSocketHandler)
server.serve_forever()
