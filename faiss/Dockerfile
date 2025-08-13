# Utilise une image Python légère
FROM python:3.10-slim

# Crée le répertoire de travail
WORKDIR /app

# Installe les dépendances système minimales
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copie les dépendances Python
COPY requirements.txt .

# Installe les packages Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie les scripts et fichiers utiles
COPY . .

# Définit le point d’entrée par défaut (modifiable)
CMD ["python"]
