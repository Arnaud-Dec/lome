# Guide d'utilisation du projet Flask + Ollama + Redis

## 🚀 Présentation du projet

Ce projet met en place une API Flask qui communique avec un serveur Ollama pour la génération de texte et utilise Redis pour gérer le contexte des conversations. L'ensemble est orchestré avec Docker Compose.

---

## 📦 Structure du projet

- `app/` : Contient l'application Flask
  - `app.py` : Code principal pour les endpoints
- `Dockerfile` : Instructions pour construire l'image Flask
- `docker-compose.yml` : Configuration des services (Flask, Ollama, Redis)
- `requirements.txt` : Liste des dépendances Python
- `volume/` : Stockage persistant pour Ollama

---

## 🔥 Lancer le projet

### 1. Démarrer les services

Assurez-vous d'avoir Docker et Docker Compose installés, puis lancez :

```bash
# Démarre Ollama, Redis et Flask
docker-compose up --build
```

Les trois services vont démarrer et être disponibles aux ports suivants :
- Flask API : http://10.144.28.121:5000
- Ollama : http://localhost:11434
- Redis : http://localhost:6379

### 2. Vérifier les logs

Vous pouvez vérifier que tout fonctionne :

```bash
docker-compose logs -f
```

---

## 🌐 Endpoints de l'API

### Healthcheck

Vérifier que le serveur Ollama est accessible :

```http
GET /healthcheck
```

Réponse attendue :

```json
{
  "status": "OK",
  "ollama_connection": "SUCCESS"
}
```

---

### Générer du texte

Envoyer un prompt et obtenir une réponse du modèle Ollama :

```http
POST /generate
```

**Body JSON:**

```json
{
  "session_id": "test_session",
  "prompt": "Dis-moi une blague !",
  "model": "llama3.2"
}
```

**Réponse:**

```json
{
  "model": "llama3.2",
  "response": "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon ils tombent dans le bateau !"
}
```

---

### Récupérer le contexte d'une session

Pour voir l'historique des échanges avec une session particulière :

```http
GET /get_context/<session_id>
```

Exemple :

```bash
curl -X GET http://10.144.28.121:5000/get_context/test_session
```

**Réponse:**

```json
{
  "context": [
    "Utilisateur: Dis-moi une blague !",
    "Assistant: Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon ils tombent dans le bateau !"
  ]
}
```

---

## ⚙️ Gestion des conteneurs Docker

### Arrêter les services

```bash
docker-compose down
```

### Nettoyer les volumes (⚠️ supprime le contexte enregistré)

```bash
docker-compose down -v
```

### Rebuilder l'image Flask

```bash
docker-compose build flask-app
```

---

## ✅ Tests rapides

Vous pouvez tester directement depuis Postman ou avec `curl`. Assurez-vous que les services sont bien lancés et écoutez les bonnes URL.

```bash
curl -X POST http://10.144.28.121:5000/generate -H "Content-Type: application/json" -d '{"session_id": "test", "prompt": "salut"}'
```
---

## 📚 Dépendances

Les dépendances sont définies dans `requirements.txt` :

```plaintext
flask==2.0.1
gunicorn==21.2.0
requests==2.26.0
werkzeug==2.0.3
redis==4.5.1
```

Installez-les localement pour les tests hors Docker :

```bash
pip install -r requirements.txt
```

---

## 🌟 Remarques

- Le contexte des conversations est stocké dans Redis et expire après 1 heure.
- Le mode streaming est activé pour Ollama pour une génération plus fluide.
- Les logs Flask sont configurés pour afficher les erreurs et les requêtes importantes.

---