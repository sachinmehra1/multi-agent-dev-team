from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/echo', methods=['POST'])
def echo():
    if request.content_type != 'application/json':
        return jsonify({'error': 'Unsupported Media Type'}), 415
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            raise ValueError('JSON is not an object')
    except Exception:
        return jsonify({'error': 'Bad Request'}), 400
    return jsonify(data)
