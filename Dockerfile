# Utiliser l'image Python 3.9-slim
FROM python:3.9-slim

# Installer curl pour les health checks
RUN apt-get update && apt-get install -y curl && apt-get clean && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier le fichier de dépendances et installer
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copier tout le projet dans le conteneur
COPY . .

# Exposer le port sur lequel Flask va tourner
EXPOSE 5000

# Lancer l'application Flask
CMD ["python", "app/app.py"]