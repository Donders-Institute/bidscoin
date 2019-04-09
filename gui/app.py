import os
from flask import Flask, render_template, jsonify

DEBUG = True

app = Flask(__name__)
app.config.from_object(__name__)


@app.route('/ping', methods=['GET'])
def ping_pong():

   



    return jsonify('pong!')


@app.route('/', methods=['GET'])
def home():
    error = None
    return render_template('index.html', error=error)


if __name__ == '__main__':
    app.run()