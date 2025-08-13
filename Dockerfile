FROM python:3.10-slim

WORKDIR /app

# 🛠️ Installer Git et outils nécessaires
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 📦 Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 📁 Copier le code source
COPY . .

# ⚙️ Définir les variables d’environnement
ENV DJANGO_SETTINGS_MODULE=config.settings

# 📄 Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput

# 🚀 Lancer Gunicorn
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]

# Pouvoir utiliser dbshell
RUN apt-get update && apt-get install -y postgresql-client
