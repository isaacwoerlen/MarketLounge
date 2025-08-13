# generate_index.py
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os

# Exemple de phrases à encoder
sentences = [
    "Le marché est en pleine croissance.",
    "Investir dans les startups est risqué.",
    "La technologie blockchain transforme la finance.",
    "Les consommateurs recherchent des produits durables.",
    "L’intelligence artificielle révolutionne le marketing."
]

# Charge le modèle SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')

# Encode les phrases en vecteurs
embeddings = model.encode(sentences, convert_to_numpy=True)

# Crée l’index FAISS
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(embeddings)

# Crée le dossier de sortie si nécessaire
output_dir = "faiss_index"
os.makedirs(output_dir, exist_ok=True)

# Sauvegarde l’index
faiss.write_index(index, os.path.join(output_dir, "index.index"))

print(f"✅ Index FAISS créé avec {len(sentences)} vecteurs.")
