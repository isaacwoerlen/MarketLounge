# 🧠 MarketLounge – Moteur de Matching Sémantique pour l’Industrie

MarketLounge est une API intelligente qui interprète les requêtes d’acheteurs industriels et les rapproche des savoir-faire d’entreprises. Elle combine matching lexical, vectoriel et contextuel, avec une architecture modulaire et évolutive.

---

## 🚀 Objectifs

- Interpréter les besoins industriels exprimés en langage naturel
- Associer ces besoins aux capacités techniques des entreprises
- Détecter des opportunités de marché à partir des signaux acheteurs
- Proposer une API monétisable et intégrable par des partenaires

---

## 🧱 Stack technique

| Composant       | Choix                                 |
|----------------|----------------------------------------|
| Backend         | Django + Django REST Framework         |
| Base de données | SQLite (local) / PostgreSQL (prod)     |
| Vector DB       | FAISS (.npy local) / Pinecone (scalable) |
| UI              | Django Templates + htmx                |
| Style           | Tailwind CSS (via CDN)                 |
| Auth            | Django auth / Auth0                    |
| Déploiement     | Docker local / VPS / Kubernetes        |
| IA              | sentence-transformers / OpenAI API     |

---

## 📁 Structure du projet

MarketLounge/ 
├── apps/ # Modules métiers │ 
	├── activation/ # Concepts activés par entreprise │ 
	├── api/ # Endpoints REST pour intégration externe │ 
	├── companies/ # Profils d’entreprise (capacités, machines…) │ 
	├── dico/ # Cerveau du moteur : concepts, synonymes, embeddings │ 
	├── glossary/ # Structure hiérarchique gouvernée (Métier → Opération → Variante) │ 
	├── logs/ # Logs de requêtes acheteurs (score, interprétation…) │ 
	├── market/ # Agrégation des signaux acheteurs (volume, région…) │ 
	└── matcher/ # Matching entre demande et profil entreprise 

├── config/ # Paramétrage Django (settings, urls, wsgi…) 
├── faiss/ # Scripts pour générer l’index vectoriel (.npy) 
├── faiss_index/ # Index FAISS prêt à l’emploi 
├── venv/ # Environnement virtuel Python 
├── .env # Variables sensibles (non versionné) 
├── .gitignore # Fichiers à exclure du versioning 
├── db.sqlite3 # Base locale (dev) 
├── docker-compose.yml # Orchestration des services 
├── Dockerfile # Image Django + Gunicorn 
├── manage.py # Entrée Django 
├── README.md # Ce fichier 
└── requirements.txt # Dépendances Python

---

## 🧪 Fonctionnalités clés

- `/api/match` : matching lexical + vectoriel
- Autocomplétion intelligente (Redis ou FAISS)
- QueryLog : journal des requêtes pour apprentissage
- Feedback utilisateur structuré
- Authentification par token ou clé API
- Monitoring et backups automatisés

---

## 🧰 Installation locale (Phase 1)

### Prérequis

- Docker & Docker Compose
- Python 3.10+
- Fichier `.npy` FAISS prêt à l’emploi

### Lancement

```bash
git clone https://github.com/ton-utilisateur/MarketLounge.git
cd MarketLounge
cp .env.example .env
docker-compose up --build
Exemple de requête
curl -X POST http://localhost:8000/api/match \
  -H "Authorization: Token <your_token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "usinage de précision"}'
________________________________________
🔐 Sécurité
•	Authentification par token ou clé API
•	HTTPS via Nginx + Certbot
•	Rate limiting (Nginx ou django-ratelimit)
•	Secrets chargés via django-environ
________________________________________
📈 Monitoring & Logs
•	Endpoint /health pour vérification
•	Logs centralisés (Django, Gunicorn, Nginx)
•	Monitoring via Prometheus + Grafana ou Uptime Kuma
•	Alertes Discord ou email en cas de crash
________________________________________
🧠 API apprenante
•	POST /company : ajout d’entreprise inconnue
•	POST /feedback : retour utilisateur (pertinent / suggestion)
•	Logs enrichis : IP, timestamp, score, user-agent
________________________________________
💰 API monétisable (Phase 3)
•	Auth par clé API + quotas
•	Dashboard utilisateur (stats, feedbacks)
•	Documentation Swagger/Redoc
•	Intégration Stripe ou LemonSqueezy
________________________________________
🧭 Roadmap
Phase	Objectif	UI recommandée
Prototype	Moteur local + API de base	Django Templates + htmx
MVP en ligne	API sécurisée + apprentissage	htmx + Tailwind
Commerciale	API monétisable + UX avancée	Next.js / React
________________________________________
📄 Documentation
•	Swagger UI
•	Redoc
•	Exemple de fiche conceptuelle : voir /apps/dico/models.py
•	Format du fichier .npy : vecteurs indexés avec FAISS
________________________________________
🤝 Contribuer
Les contributions sont les bienvenues ! Ouvre une issue ou un pull request pour proposer une amélioration ou corriger un bug.
________________________________________
📜 Licence
Ce projet est sous licence MIT.
________________________________________
✨ Remerciements
Merci à tous ceux qui croient en une industrie plus intelligente, plus connectée, et plus accessible.

---

