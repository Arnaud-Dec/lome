from flask import Flask, request, jsonify
import requests, time, os, json, redis
import datetime
app = Flask(__name__)


# Récupérer les informations de connexion depuis les variables d'environnement
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'ollama-server')
OLLAMA_PORT = os.environ.get('OLLAMA_PORT', '11434')
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))

OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
MAX_RETRIES = 5
RETRY_DELAY = 2  # secondes

# Connexion à Redis
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

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

def get_timestamp():
    return datetime.datetime.now().isoformat()

def format_context_for_prompt(context):
    formatted = []
    for msg in context:
        timestamp = msg.get("timestamp", "inconnu")
        author = "Utilisateur" if msg["author"] == "user" else "Assistant"
        content = msg["content"]
        formatted.append(f"[{timestamp}] {author}: {content}")
    return "\n".join(formatted)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    session_id = data.get('session_id', 'default_session')
    prompt = data.get('prompt', '')
    model = data.get('model', 'llama3.2')

    # Récupérer le contexte
    stored_context = redis_client.get(session_id)
    context = json.loads(stored_context) if stored_context else []

    # Ajouter le prompt actuel avec un timestamp
    context.append({
        "timestamp": get_timestamp(),
        "author": "user",
        "content": prompt
    })

    # Formater le contexte pour le prompt d'Ollama
    formatted_context = format_context_for_prompt(context)
    full_prompt = f"{formatted_context}\n[Maintenant] Utilisateur: {prompt}"

    data_to_send = {
        'prompt': full_prompt,
        'model': model
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=data_to_send,
            headers={'Content-Type': 'application/json'},
            timeout=120,
            stream=True
        )
        response.raise_for_status()

        full_response = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                full_response += chunk.get("response", "")
                if chunk.get("done", False):
                    break

        # Ajouter la réponse du bot avec un timestamp
        context.append({
            "timestamp": get_timestamp(),
            "author": "bot",
            "content": full_response
        })

        redis_client.set(session_id, json.dumps(context))
        redis_client.expire(session_id, 3600)

        return jsonify({
            'model': model,
            'response': full_response
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur lors de la connexion à Ollama: {e}")
        return jsonify({"error": "Erreur de connexion à Ollama"}), 500
    except Exception as ex:
        app.logger.error(f"Erreur lors du parsing JSON: {ex}")
        return jsonify({"error": "Erreur de parsing JSON"}), 500



@app.route('/get_context/<session_id>', methods=['GET'])
def get_context(session_id):
    stored_context = redis_client.get(session_id)
    if stored_context:
        context = json.loads(stored_context)
        return jsonify({"context": context})
    return jsonify({"context": []}), 404

if __name__ == '__main__':
    app.logger.info(f"Démarrage du service Flask. En attente de connexion à Ollama sur {OLLAMA_URL}")
    app.run(debug=True, host='0.0.0.0')