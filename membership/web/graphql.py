import json

from flask import Blueprint, jsonify, request

from membership.database.base import Session
from membership.database.models import Member
from membership.schemas.graphql import schema
from membership.web.auth import authentication, error_response
from typing import Optional

graphql_api = Blueprint('graphql_api', __name__)


@graphql_api.route('/graphql', methods=['GET', 'POST'])
@authentication(required=True)
def query(requester: Member, session: Session):
    # this should match the following spec:
    # http://graphql.org/learn/serving-over-http/#http-methods-headers-and-body

    # get the query
    # from the body if the content type is graphql, regardless of request method
    if request.content_type.lower() == 'application/graphql':
        graphql_query = request.data
    # from the query string if GET request
    elif request.method == 'GET':
        graphql_query = request.args.get('query', '')
    # if not a GET request, handle the ambiguity of multiple query parameters
    elif 'query' in request.args and 'query' in request.json:
        return error_response(400, ['"query" parameter cannot be in both query string and request body'])
    # from the request body as json if POST request
    else:
        graphql_query = request.json.get('query', '')

    # validate the query
    if graphql_query == '':
        return error_response(400, ['GraphQL query cannot be empty'])

    # get the variables
    # from the query string if POST request
    if request.method == 'GET':
        graphql_variables = json.loads(request.args.get('variables', '{}'))
    # from the request body as json if POST request
    else:
        graphql_variables = request.json.get('variables', {})

    # execute the query with the provided variables
    result = schema.execute(graphql_query, context_value={
        'session': session,
        'requester': requester,
    }, variable_values=graphql_variables)
    if result.errors:
        return error_response(400, result.errors)
    else:
        return jsonify({'data': result.data})
