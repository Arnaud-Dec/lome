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

    # Si c'est une nouvelle session, ajouter le prompt système pour guider LOME
    if not context:
        startup_prompt = {
            "timestamp": get_timestamp(),
            "author": "system",
            "content": (
                "Tu es LOME, un assistant intelligent spécialisé dans le contrôle des lumières d'une maison, "
                "mais tu es également capable de répondre à des questions générales de manière informative et détaillée. "
                "Pour chaque réponse que tu fournis, tu dois renvoyer un JSON avec exactement deux champs :\n\n"
                
                "1. **response** : une chaîne de caractères contenant ta réponse textuelle destinée à l'utilisateur.\n"
                "2. **command** : un objet JSON qui contient la commande à exécuter. Si la demande concerne le contrôle des lumières, "
                "tu dois générer un JSON précis avec deux clés ; sinon, ce champ doit être un objet vide ({}).\n\n"
                
                "### Instructions détaillées :\n\n"
                
                "A. **Si la demande concerne le contrôle des lumières** (par exemple, allumer, éteindre ou modifier une lumière) :\n"
                "   - Dans le champ **response**, commence par une phrase naturelle qui informe l'utilisateur (par exemple :\n"
                "     \"Très bien, j'allume la lumière du salon.\").\n"
                "   - Ensuite, sur une nouvelle ligne, renvoie EXACTEMENT un JSON contenant deux clés :\n"
                "       - \"nom\" : le nom de la lumière concernée (ex. \"lumiere salon\").\n"
                "       - \"action\" : l'action à réaliser, soit \"on\" pour allumer ou \"off\" pour éteindre.\n\n"
                
                "   **Exemple complet :**\n"
                "   - **Entrée utilisateur :** \"allume lumiere 1\"\n"
                "   - **Réponse attendue :**\n"
                "     {\n"
                "       \"response\": \"Très bien, j'allume la lumière 1.\",\n"
                "       \"command\": {\"nom\": \"lumiere 1\", \"action\": \"on\"}\n"
                "     }\n\n"
                
                "B. **Si la demande est générale (non liée aux lumières)** :\n"
                "   - Dans le champ **response**, répond de manière classique et naturelle (ex. raconter une histoire, donner une information, etc.).\n"
                "   - Le champ **command** doit être un objet vide : {}\n\n"
                
                "   **Exemples :**\n"
                "   1. **Entrée utilisateur :** \"raconte une petite histoire de 200 mots pour mon enfant\"\n"
                "      **Réponse attendue :**\n"
                "      {\n"
                "        \"response\": \"Bien sûr ! Voici une petite histoire pour ton enfant : Il était une fois...\",\n"
                "        \"command\": {}\n"
                "      }\n\n"
                "   2. **Entrée utilisateur :** \"quelle est la capitale du Mali ?\"\n"
                "      **Réponse attendue :**\n"
                "      {\n"
                "        \"response\": \"La capitale du Mali est Bamako.\",\n"
                "        \"command\": {}\n"
                "      }\n\n"
                
                "C. **Si l'utilisateur demande ton identité** :\n"
                "   - **Entrée utilisateur :** \"comment tu t'appelles ?\"\n"
                "   - **Réponse attendue :**\n"
                "     {\n"
                "       \"response\": \"Je m'appelle LOME, enchanté de vous aider !\",\n"
                "       \"command\": {}\n"
                "     }\n\n"
                
                "### Format final obligatoire :\n"
                "Chaque réponse doit être un JSON ayant exactement la structure suivante :\n\n"
                "{\n"
                "  \"response\": \"<texte de la réponse>\",\n"
                "  \"command\": <objet JSON exact pour la commande ou {}>\n"
                "}\n\n"
                
                "Important :\n"
                "- Si la demande **concerne le contrôle des lumières**, assure-toi que le JSON dans le champ \"command\" "
                "est exactement généré comme dans l'exemple et qu'il n'inclut aucune annotation supplémentaire.\n"
                "- Si la demande **n'est pas liée aux lumières**, réponds normalement dans le champ \"response\" et mets {} dans \"command\".\n"
                "-la réponse doit être au format JSON valide, sans texte supplémentaire ni explications.\n"
                "-Ne jamais inclure de texte supplémentaire en dehors du JSON.\n"
                "-Ne pas dépacer 200 mots dans la réponse.\n\n"
                
                "Respecte strictement ces instructions pour éviter toute confusion et garantir une structure de réponse cohérente."
            )
        }
        context.append(startup_prompt)

    # Ajouter le message de l'utilisateur
    context.append({
        "timestamp": get_timestamp(),
        "author": "user",
        "content": prompt
    })

    # Construire le prompt complet envoyé à Ollama
    formatted_context = format_context_for_prompt(context)
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

        full_response_str = full_response.strip()
        command = {}
        message = ""

        # Essayer de parser la réponse complète comme JSON
        try:
            parsed_response = json.loads(full_response_str)
            if isinstance(parsed_response, dict) and "response" in parsed_response and "command" in parsed_response:
                message = parsed_response["response"]
                command = parsed_response["command"]
            else:
                message = full_response_str
        except Exception:
            # Si ce n'est pas un JSON complet, on cherche le dernier "{" pour extraire le JSON de commande
            json_index = full_response_str.rfind('{')
            if json_index != -1:
                possible_json = full_response_str[json_index:]
                try:
                    command = json.loads(possible_json)
                    message = full_response_str[:json_index].strip()
                except Exception as ex:
                    app.logger.error(f"Erreur lors du parsing du JSON de commande: {ex}")
                    message = full_response_str
                    command = {}
            else:
                message = full_response_str
                command = {}

        # Ajouter la réponse du bot avec timestamp dans le contexte
        context.append({
            "timestamp": get_timestamp(),
            "author": "bot",
            "content": full_response
        })

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
    app.logger.info(f"Démarrage du service Flask sur ZeroTier (accessible via 10.144.28.121:5000)")
    app.run(debug=True, host='0.0.0.0', port=5000)
