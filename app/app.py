from flask import Flask, request, jsonify
import requests, time, os, json, redis, datetime

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
        # On considère "system" comme Système si présent
        if msg["author"] == "user":
            author = "Utilisateur"
        elif msg["author"] == "bot":
            author = "Assistant"
        elif msg["author"] == "system":
            author = "Système"
        else:
            author = msg["author"]
        content = msg["content"]
        formatted.append(f"[{timestamp}] {author}: {content}")
    return "\n".join(formatted)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    session_id = data.get('session_id', 'default_session')
    prompt = data.get('prompt', '')
    model = data.get('model', 'llama3.2')

    # Récupérer le contexte existant
    stored_context = redis_client.get(session_id)
    context = json.loads(stored_context) if stored_context else []

    # Si c'est une nouvelle session, ajouter le prompt système pour guider le bot
    if not context:
        startup_prompt = {
            "timestamp": get_timestamp(),
            "author": "system",
            "content": (
                "Tu es LOME, un HomeAssistant spécialisé dans le contrôle des lumières dans une maison. "
                "Ton rôle est strictement de recevoir et d'exécuter des commandes pour allumer ou éteindre les lumières, "
                "et de répondre de manière claire aux utilisateurs.\n\n"
                "Instructions pour répondre aux commandes concernant les lumières :\n"
                "1. Si la demande concerne le contrôle des lumières, répond d'abord par une phrase claire destinée à l'utilisateur "
                "(par exemple : \"Très bien, j'allume la lumière du salon\").\n"
                "2. Ensuite, sur une nouvelle ligne, renvoie un JSON EXACT contenant exactement deux champs :\n"
                "   - \"nom\" : le nom de la lumière (par exemple, \"lumiere salon\").\n"
                "   - \"action\" : l'action à effectuer, qui peut être \"on\" ou \"off\".\n\n"
                "Par exemple, pour la commande \"allume lumière 1\", ta réponse doit ressembler à :\n"
                "Très bien, j'allume la lumière 1.\n"
                "{\"nom\": \"lumiere 1\", \"action\": \"on\"}\n\n"
                "Si la demande ne concerne pas le contrôle des lumières, répond de manière classique sans inclure de JSON dans ta réponse.\n\n"
                "Rappelle-toi : tu t'appelles LOME et ton objectif principal est de contrôler les lumières en suivant ces instructions précises."
            )
        }
        context.append(startup_prompt)

    # Ajouter le message de l'utilisateur avec un timestamp
    context.append({
        "timestamp": get_timestamp(),
        "author": "user",
        "content": prompt
    })

    # Construire le prompt complet envoyé à Ollama
    formatted_context = format_context_for_prompt(context)
    # On peut ajouter une marque indiquant le moment actuel
    full_prompt = f"{formatted_context}\n[Maintenant] Utilisateur: {prompt}"

    data_to_send = {
        'prompt': full_prompt,
        'model': model
    }

    try:
        app.logger.info(f"Envoi de la requête à Ollama: {OLLAMA_URL}")
        response = requests.post(
            OLLAMA_URL,
            json=data_to_send,
            headers={'Content-Type': 'application/json'},
            timeout=120,
            stream=True
        )
        response.raise_for_status()

        full_response = ""
        # Accumuler les chunks de réponse
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode('utf-8'))
                full_response += chunk.get("response", "")
                if chunk.get("done", False):
                    break

        # Heuristique pour les commandes de lumière
        light_keywords = ["lumiere", "lumière", "allume", "allumer", "éteins", "eteins", "éteindre"]
        command = {}
        message = full_response.strip()
        if any(kw in prompt.lower() for kw in light_keywords):
            # Si le prompt contient un mot-clé, on essaie d'extraire le JSON à la fin de la réponse
            lines = full_response.strip().splitlines()
            if lines:
                possible_json = lines[-1]
                try:
                    command = json.loads(possible_json)
                    message = "\n".join(lines[:-1]).strip()
                except Exception as ex:
                    app.logger.error(f"Erreur lors du parsing du JSON de commande: {ex}")
                    command = {}

        # Ajouter la réponse du bot avec un timestamp au contexte
        context.append({
            "timestamp": get_timestamp(),
            "author": "bot",
            "content": full_response
        })

        # Sauvegarder le contexte dans Redis (expiration d'une heure)
        redis_client.set(session_id, json.dumps(context))
        redis_client.expire(session_id, 3600)

        return jsonify({
            'model': model,
            'response': message,
            'command': command
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
