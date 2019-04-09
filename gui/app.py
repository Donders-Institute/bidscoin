import os
from flask import Flask, render_template, jsonify
from flask_cors import CORS

# configuration
DEBUG = True

# instantiate the app
app = Flask(__name__)
app.config.from_object(__name__)

# enable CORS
CORS(app)


@app.route('/ping', methods=['GET'])
def ping_pong():
    error = None
    return jsonify('pong!')

# sanity check route
@app.route('/', methods=['GET'])
def home():
    error = None
    return render_template('index.html', error=error)


if __name__ == '__main__':
    app.run()