# Utiliser l'image Python 3.9-slim
FROM python:3.9-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier le fichier de dépendances et installer
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copier tout le projet dans le conteneur
COPY . .

# Exposer le port sur lequel Flask va tourner
EXPOSE 5000

# Lancer l'application Flask (le fichier se trouve dans le dossier app)
CMD ["python", "app/app.py"]
