import json
import logging
import random
import string
import traceback
from datetime import datetime, timedelta
from functools import wraps
from typing import List, Optional, Union

import jwt
import requests
from flask import request, Response, jsonify

from config.auth_config import JWT_SECRET, JWT_CLIENT_ID, ADMIN_CLIENT_ID, ADMIN_CLIENT_SECRET, \
    AUTH_CONNECTION, AUTH_URL, USE_AUTH, NO_AUTH_EMAIL
from config.portal_config import PORTAL_URL
from membership.database.base import Session
from membership.database.models import Member

PASSWORD_CHARS = string.ascii_letters + string.digits


def deny(reason: str= '') -> Response:
    """Sends a 401 response that enables basic auth"""
    response = jsonify({
        'status': 'error',
        'err': 'Could not verify your access level for that URL.\n'
               'You have to login with proper credentials and' + reason
    })
    response.status_code = 401
    return response


def exc_json(error: Exception):
    return {
        'type': type(error).__name__,
        'message': str(error),
        # TODO: Only show traceback if development mode
        'traceback': traceback.format_exception(None, error, error.__traceback__),
    }


def error_response(status: int, errors: Optional[List[Union[str, dict, Exception]]] = None) -> Response:
    """
    Serializes the given errors into a response object with the given status.

    :param status: The status code of the response
    :param errors: An optional list of errors to put in the response body, if None then the response body will be empty
    :return: a Response object with the given status code and the errors serialized as json
    """
    if errors is None:
        response_body = None
    elif isinstance(errors, list):
        response_errors = []
        for e in errors:
            if isinstance(e, Exception):
                response_errors.append(exc_json(e))
            elif isinstance(e, (dict, str)):
                response_errors.append(e)
            else:
                raise Exception('Cannot serialize error of type {}: {}'.format(type(e), e))
        response_body = json.dumps({'errors': response_errors})
    else:
        raise Exception('Illegal argument for errors. Must be a list, not {}: {}'.format(type(errors), errors))
    return Response(response=response_body, status=status)


def authentication(required: bool=False):
    """
    A decorator that performs authentication without authorization.

    This allows the controller function to define the behavior of authorization based on parameters.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if USE_AUTH:
                auth = request.headers.get('authorization')
                if auth:
                    token = auth.split()[1]
                    try:
                        token = jwt.decode(token, JWT_SECRET, audience=JWT_CLIENT_ID)
                    except Exception as e:
                        return error_response(401, [e])
                    email = token.get('email')
                elif not required:
                    email = None
                else:
                    return error_response(401, ['Authentication required'])
            else:
                email = NO_AUTH_EMAIL
            session = Session()
            try:
                if email is None:
                    requester = None
                else:
                    requester = session.query(Member).filter_by(email_address=email).one()
                kwargs['requester'] = requester
                kwargs['session'] = session
                return f(*args, **kwargs)
            finally:
                session.close()

        return decorated
    return decorator


def requires_auth(admin=False):
    """ This defines a decorator which when added to a route function in flask requires authorization to
    view the route.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if USE_AUTH:
                auth = request.headers.get('authorization')
                if not auth:
                    return deny('Authorization not found.')
                token = auth.split()[1]
                try:
                    token = jwt.decode(token, JWT_SECRET, audience=JWT_CLIENT_ID)
                except Exception as e:
                    return deny(str(e))
                email = token.get('email')
            else:
                email = NO_AUTH_EMAIL
            session = Session()
            try:
                member = session.query(Member).filter_by(email_address=email).one()
                authenticated = False
                if admin:
                    for role in member.roles:
                        if role.committee_id is None and role.role == 'admin':
                            authenticated = True
                else:
                    authenticated = True
                if authenticated:
                    kwargs['requester'] = member
                    kwargs['session'] = session
                    return f(*args, **kwargs)
                return deny('not enough access')
            finally:
                session.close()

        return decorated
    return decorator


current_token = {}


def get_auth0_token():
    if not current_token or datetime.now() > current_token['expiry']:
        current_token.update(generate_auth0_token())
    return current_token['token']


def generate_auth0_token():
    payload = {'grant_type': "client_credentials",
               'client_id': ADMIN_CLIENT_ID,
               'client_secret': ADMIN_CLIENT_SECRET,
               'audience': AUTH_URL + 'api/v2/'}
    response = requests.post(AUTH_URL + 'oauth/token', json=payload).json()
    return {'token': response['access_token'],
            'expiry': datetime.now() + timedelta(seconds=response['expires_in'])}


def create_auth0_user(email):
    if not USE_AUTH:
        return PORTAL_URL
    # create the user
    payload = {
        'connection': AUTH_CONNECTION,
        'email': email,
        'password': ''.join(random.SystemRandom().choice(PASSWORD_CHARS) for _ in range(12)),
        'user_metadata': {},
        'email_verified': False,
        'verify_email': False
    }
    headers = {'Authorization': 'Bearer ' + get_auth0_token()}
    r = requests.post(AUTH_URL + 'api/v2/users', json=payload, headers=headers)
    if r.status_code > 299:
        logging.error(r.json())
        raise Exception('Failed to create user')
    user_id = r.json()['user_id']

    # get a password change URL
    payload = {
        'result_url': PORTAL_URL,
        'user_id': user_id
    }
    r = requests.post(AUTH_URL + 'api/v2/tickets/password-change', json=payload, headers=headers)
    if r.status_code > 299:
        logging.error(r.json())
        raise Exception('Failed to get password url')
    reset_url = r.json()['ticket']

    # get email verification link
    payload = {
        'result_url': reset_url,
        'user_id': user_id
    }
    r = requests.post(AUTH_URL + 'api/v2/tickets/email-verification', json=payload, headers=headers)
    if r.status_code > 299:
        logging.error(r.json())
        raise Exception('Failed to get verify url')
    validate_url = r.json()['ticket']
    return validate_url

