from flask import Flask, request, jsonify
import requests
import time
import os
import json


app = Flask(__name__)

# Paramètres et constantes
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'ollama-server')
OLLAMA_PORT = os.environ.get('OLLAMA_PORT', '11434')
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds

@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    """Endpoint de vérification de l'état du serveur Ollama"""
    try:
        response = requests.get(f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")
        if response.status_code == 200:
            return jsonify({"status": "OK", "ollama_connection": "SUCCESS"})
        return jsonify({"status": "OK", "ollama_connection": "FAILED", "status_code": response.status_code})
    except Exception as e:
        return jsonify({"status": "OK", "ollama_connection": "ERROR", "error": str(e)})


@app.route('/generate', methods=['POST'])
def generate():
    data = {
        'prompt': request.json.get('prompt'),
        'model': request.json.get('model', 'llama3.2')
    }

    try:
        app.logger.info(f"Envoi de la requête à Ollama : {OLLAMA_URL}")
        response = requests.post(
            OLLAMA_URL,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=120,  # Augmenter le timeout pour les longues générations
            stream=True   # Active le mode streaming
        )

        response.raise_for_status()

        # Récupération des chunks et concaténation
        full_response = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                full_response += chunk.get("response", "")
                if chunk.get("done", False):
                    break

        return jsonify({
            'model': data['model'],
            'response': full_response
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur de connexion à Ollama : {e}")
        return jsonify({'error': f"Erreur de connexion : {str(e)}"}), 500


@app.route('/', methods=['GET'])
def home():
    return "API Flask fonctionne! Utilisez /generate pour les requêtes LLM et /healthcheck pour vérifier la connexion à Ollama."

if __name__ == '__main__':
    # Attendre que le serveur Ollama soit disponible
    app.logger.info(f"Démarrage du service Flask. En attente de connexion à Ollama sur {OLLAMA_URL}")
    app.run(debug=True, host='0.0.0.0')