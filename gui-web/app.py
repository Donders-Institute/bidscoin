import os
import ruamel.yaml as yaml
from flask import Flask, render_template, jsonify

DEBUG = True

app = Flask(__name__)
app.config.from_object(__name__)


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


def derive_unknown(contents):
    """ """
    unknown = []
    contents = contents.get('DICOM', {})
    for item in contents.get('extra_data', []):
        provenance = item.get('provenance', None)
        if provenance:
            unknown.append({
                "provenance_path": os.path.dirname(provenance),
                "provenance_file": os.path.basename(provenance) 
            })
    return unknown



@app.route('/ping', methods=['GET'])
def ping_pong():

    with open('../tests/testdata/bidsmap_example_new.yaml') as stream:
        try:
            contents = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise InvalidUsage('Error: %s' % exc, status_code=410)

    unknown = derive_unknown(contents)
    return jsonify(unknown)


@app.route('/', methods=['GET'])
def home():
    error = None
    return render_template('index.html', error=error)


if __name__ == '__main__':
    app.run()