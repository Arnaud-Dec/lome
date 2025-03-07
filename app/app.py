from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    data = {
        'prompt': request.json.get('prompt'),
        'model': 'llama3.2'
    }
    try:
        response = requests.post(
            'http://ollama-server:11434/api/generate',
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return "API Flask fonctionne !"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
