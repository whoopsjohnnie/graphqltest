import graphql
import json

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

resolvers = {
  
}


my_schema = build_executable_schema(source_schema, resolvers)
