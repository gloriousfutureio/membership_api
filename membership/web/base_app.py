from flask import jsonify
from flask import Flask
from flask_cors import CORS
from membership.web.members import member_api
from membership.web.elections import election_api
from membership.web.graphql import graphql_api
from raven.contrib.flask import Sentry

app = Flask(__name__)
CORS(app)
app.register_blueprint(member_api)
app.register_blueprint(election_api)
app.register_blueprint(graphql_api)
sentry = Sentry(app)


@app.route('/health', methods=["GET"])
def health_check():
    return jsonify({'health': True})
