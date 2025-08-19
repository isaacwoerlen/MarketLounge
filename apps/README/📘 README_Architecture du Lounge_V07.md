📘 Architecture du moteur Lounge (V07)

🧭 INTRODUCTIONCe document décrit l’architecture du moteur sémantique de The Lounge, conçu pour connecter les requêtes acheteurs aux capacités techniques des entreprises via un matching sémantique gouverné. Il interprète des requêtes complexes (ex. : « inox 316 pour aéro dans le 59 ») pour identifier des concepts métier activables et générer une shortlist d’entreprises pertinentes. L’architecture est modulaire, évolutive, et centrée sur la réalité industrielle.  
Ce document est aligné avec README Brief Technique.md, qui détaille l’implémentation technique (stack, conventions dev). V07 remplace V04/06 ; chapitres renumérotés pour refléter le flux logique (offline → runtime → apprentissage).
Principes No-Overlap

Chaque app a un rôle unique, sans chevauchement.  
Exemple : dico génère concepts offline ; matching exécute matching runtime ; curation valide humainement.  
Tâches offline/runtime strictement séparées ; délégations via modèle "pull".  
Pas de modification directe des données d’une autre app ; appels explicites.

Flux Global des Apps
graph TD  
    CompanyProfile -->|Facettes brutes| Dico[Offline: Génération concepts]  
    Glossaire -->|Validation| Dico  
    Dico -->|Concepts validés| Activation[Offline: Index activations]  
    Activation -->|Activations| Matching[Runtime: Hybrid search]  
    Requête -->|NLP| Matching  
    Matching -->|Shortlist + Scores| Logs[Traçabilité]  
    Logs -->|Feedback/Proposals| Curation[Validation humaine]  
    Curation -->|Enrichissements validés| Dico  
    Market -->|Analyse| Logs  


🧱 Piliers Fonctionnels  

Glossaire Métier : Structure stable des savoir-faire (Métier → Opération → Variante). Rôle : Validation canonique.  
Company Profile : Déclaration brute des capacités. Rôle : Collecte facettes sans interprétation.  
Dictionnaire Sémantique (Dico) : Génération offline de concepts activables. Rôle : Création/enrichissement statique.  
Company Concept Activation : Indexation runtime des savoir-faire activés. Rôle : Fournir activations pour matching.


@@ -10,6 +10,10 @@
 Principes No-Overlap
 
 Chaque app a un rôle unique, sans chevauchement.  
+Multi-tenancy Global : Toutes les apps gérant des données sensibles (ex. : company, activation, glossary, market) supportent le multi-tenancy via un champ tenant_id (validé par regex ^tenant_[a-zA-Z0-9_]+$). Cela permet sharding par tenant pour scalabilité (ex. : partition DB PostgreSQL). Les transverses comme language/LLM_ai appliquent cela aux jobs/modèles pour isolation.
+
 Exemple : dico génère concepts offline ; matching exécute matching runtime ; curation valide humainement.  
 Tâches offline/runtime strictement séparées ; délégations via modèle "pull".  
 Pas de modification directe des données d’une autre app ; appels explicites.
@@ -300,6 +304,7 @@
 
 App
 Type
+Multi-tenancy
 Chapitre
 Rôle (strict)
 Technos
@@ -307,6 +312,7 @@
 Flux Sortants
 Limites
 
+✅ (tenant_id)
 glossary
 Verticale
 1
@@ -314,6 +320,7 @@
 PostgreSQL, JSONField
 -
 Refs → Dico
+✅ (tenant_id)
 Pas enrichissement/matching
 
 company
@@ -321,6 +328,7 @@
 2
 Collecte facettes
 PostgreSQL, societe.com
+✅ (tenant_id)
 -
 Facettes → Dico
 Pas génération
@@ -328,6 +336,7 @@
 dico
 Verticale
 3, 4
+✅ (tenant_id sur concepts)
 Génération concepts offline
 pgvector, sentence-transformers, LLM_ai
 Facettes (Company), Refs (Glossaire), Proposals (Curation)
@@ -335,6 +344,7 @@
 Offline only
 
 matching
+✅ (tenant_id sur recherches)
 Verticale
 6, 7
 Matching runtime
@@ -342,6 +352,7 @@
 Concepts (Dico), Activations (Activation), Requête
 Shortlist → Logs
 Runtime only
+✅ (tenant_id sur index)
 
 activation
 Verticale
@@ -349,6 +360,7 @@
 Index activations
 PostgreSQL
 Concepts (Dico)
+✅ (tenant_id sur logs)
 Activations → Matching
 Index only
 
@@ -356,6 +368,7 @@
 Verticale
 8
 Tracer requêtes
+✅ (tenant_id sur insights)
 PostgreSQL, metrics
 Shortlist (Matching)
 Feedback → Curation/Market
@@ -363,6 +376,7 @@
 
 market
 Verticale
+✅ (tenant_id sur proposals)
 9
 Analyse marché
 pgvector, LLM_ai
@@ -370,6 +384,7 @@
 Insights
 Pas SEO/matching
 
+✅ (tenant_id global)
 curation
 Verticale
 10
@@ -377,6 +392,7 @@
 Django admin, Celery, LLM_ai
 Feedback (Logs)
 Proposals → Dico
+✅ (tenant_id sur traductions)
 Pas enrichissement
 
 language
@@ -384,6 +400,7 @@
 Tous
 Traduction
 Mistral API
+✅ (tenant_id sur appels)
 Appels pull
 Traductions
 Appel pull only

🧩 Portée du MVP  

Core MVP : glossary, company, dico, activation, matching, logs.  
V1.1+ : market, curation, fonctionnalités SEO, feedback utilisateur.


🧠 Limites Globales  



App
Limite
Justification



glossary
Pas d’enrichissement/matching
Fournit structure stable


company
Pas de génération concepts
Collecte facettes brutes


dico
Offline only ; pas de matching
Génère/enrichit concepts


matching
Runtime only ; pas de génération
Exécute hybrid search


activation
Index only ; pas de search
Fournit activations


market
Pas de SEO/matching
Analyse marché


logs
Logs purs ; pas d’analyse
Trace requêtes/scores


curation
Pas d’enrichissement direct
Valide proposals



📚 GLOSSAIRE MÉTIER🎯 RôleColonne vertébrale sémantique : définit nœuds métier typés (métier, opération, variante).Rôle dédié : Fournir structure stable pour validation offline par dico.


Définir nœuds gouvernés  
Produire node_id stables  
Fournir descriptions riches  
Générer paths contextuels  
Fournir tags/related_to

⚙️ Structure  



Attribut
Description



node_id
Identifiant stable (ex. fraisage_cn)


type
Métier, opération, variante


labels
Noms multilingues


definition
Définition précise


procédé
Méthode technique


explication_technique
Détail industriel


contextual_description
Bloc vectorisable


paths
Chemins contextuels


tags
Mots-clés


related_to
Liens faibles


status
draft, validated, deprecated


version
Version nœud


🧩 ArticulationUtilisé par dico pour validation offline. Délègue matching à matching.  

🏭 COMPANY PROFILE🎯 RôleDéclaration brute entreprise : collecte facettes (opérations, matières, machines).Rôle dédié : Fournir facettes sans interprétation.


Créer profil (API, scraping, manuel)  
Déclarer facettes  
Valider via curation

⚙️ Structure  



Attribut
Description



company_id
Identifiant entreprise


facettes
Opérations, matières, machines


source
API, scraping, manuel


🧩 ArticulationFacettes → dico pour génération concepts. Pas de lien runtime direct.  

🧠 DICTIONNAIRE SÉMANTIQUE (DICO)🎯 RôleCerveau offline : génère concepts activables (concept_ID).Rôle dédié : Création/enrichissement statique offline.


Créer concept_IDs  
Enrichir (synonymes, embeddings)  
Exposer à matching

⚙️ Structure  



Attribut
Description



concept_ID
Identifiant stable


labels
Noms multilingues


definition
Définition précise


synonyms
Variantes lexicales


related_to
Liens faibles


tags
Mots-clés


embedding
Vecteur statique


glossary_node_ids
Références Glossaire


path
Chemin contextuel


contextual_description
Bloc enrichi


🔄 Cycle[Company Profile] → [Facettes] → [Dico offline] → [Concept proposé] → [Glossaire validation] → [Curation validation] → [Concept_ID] → [Indexation Dico]  
🧩 ArticulationFacettes (company), Réfs (glossary), Proposals (curation) → Concepts → activation/matching.  

📚 GÉNÉRATION ET USAGE DES CONCEPT_ID🎯 RôleGénération offline (concept_IDs) ; usage runtime (matching, indexation, analyse).


Générer via dico  
Utiliser dans matching, activation, market

🧬 Sources  



Source
Rôle
Crée concept_ID ?



Glossaire
Structure stable
✅ Base sémantique


Company Profile
Facettes
✅ Source usage


Requêtes
Signal usage
❌ Nourrit proposals


⚙️ Processus (offline)  

Analyse facettes (dico)  
Mapping Glossaire  
Enrichissement statique  
Validation via curation

🧩 Articulationdico → activation (indexation), matching (runtime), market (analyse).  

🚀 ACTIVATION DES CONCEPTS🎯 RôleIndex runtime des savoir-faire activés.Rôle dédié : Indexer activations offline pour matching.


Activer concept_ID  
Indexer facettes  
Stocker evidence

⚙️ Structure  



Attribut
Description



company_id
Identifiant entreprise


concept_ID
Concept activé


facettes
Tags associés


evidence
Justification


is_claimed
Revendiqué


🔄 Cycle[Company Profile] → [Facettes] → [Dico] → [Concept_IDs] → [Activation offline] → [Index Activation]  
🧩 ArticulationConcepts (dico) → Activations → matching.  

🧠 MATCHING🎯 RôleMatching runtime hybrid (lexical + vectoriel) sur concepts de dico.Rôle dédié : Exécuter matching, cache résultats via Redis.


NLP + parsing requête  
Matching lexical/vectoriel  
Fusion/scoring  
Filtrage via activation

⚙️ Hybrid Search  
graph TD  
    A[Requête] --> B[NLP]  
    B --> C1[Lexical]  
    B --> C2[Vectoriel]  
    C1 --> D[Fusion]  
    C2 --> D  
    D --> E[Filtrage Activation]  
    E --> F[Shortlist]  
    F --> G[Logs]  

🧩 Composants  



Composant
Rôle



company_profile
Source brute


dico
Concepts offline


activation
Filtrage


logs
Observabilité


🧩 ArticulationConcepts (dico), Activations (activation), Requête → Shortlist → logs.  

🧠 MOTEUR D’EXPLICABILITÉ🎯 RôleJustifier décisions runtime via matching.Rôle dédié : Générer/stocker explications.


Produire justifications (scores, relations)  
Stocker dans logs

⚙️ Fonctionnement  
graph TD  
    A[Requête] --> B[Matching]  
    B --> C[Shortlist]  
    C --> D[Explicabilité]  
    D --> E[Logs]  

🧩 Types d’Explication  



Type
Exemple



Relation
“Relié via ‘proche_de’”


Score
“Cosine 0.88”


Exclusion
“Non activé”


🧩 ArticulationConcepts (dico), Activations (activation) → Explications (matching) → logs.  

🧠 REQUEST_ID & QUERY MATCH LOG🎯 RôleObservabilité runtime via logs.Rôle dédié : Tracer requêtes/scores.


Assigner request_ID  
Logger texte, concept_ID, scores  
Alimenter curation/market

🧩 ArticulationShortlist/scores (matching) → Feedback → curation/market.  

🧠 MARKET INTELLIGENCE🎯 RôleAnalyse marché via market.Rôle dédié : Croiser offre/demande sans SEO/matching.


Détecter tensions/raretés  
Produire insights

🧩 ArticulationLogs (logs), Activations (activation) → Insights (API/UI).  

🔄 CYCLE D’APPRENTISSAGE🎯 RôleAmélioration asynchrone via curation.Rôle dédié : Valider proposals (Django admin/CLI).


Valider humainement  
Enrichir via dico

🔁 Flux  
graph TD  
    A[Requête] --> B[Matching]  
    B --> C[Logs]  
    C --> D[Curation]  
    D --> E[Proposals]  
    E --> F[Validation]  
    F --> G[Dico]  

🧩 Enrichissements  



Type
Exemple



Lexical
“usinage 5 axes” → “fraisage multi-axes”


Sémantique
“découpe laser” proche “jet d’eau”


🧩 ArticulationFeedback (logs) → Proposals (curation) → Enrichissements (dico).  
📊 Tableau des Apps



App
Type
Chapitre
Rôle (strict)
Technos
Flux Entrants
Flux Sortants
Limites



glossary
Verticale
1
Structure stable
PostgreSQL, JSONField
-
Refs → Dico
Pas enrichissement/matching


company
Verticale
2
Collecte facettes
PostgreSQL, societe.com
-
Facettes → Dico
Pas génération


dico
Verticale
3, 4
Génération concepts offline
pgvector, sentence-transformers, LLM_ai
Facettes (Company), Refs (Glossaire), Proposals (Curation)
Concepts → Activation/Matching
Offline only


matching
Verticale
6, 7
Matching runtime
FAISS, pgvector, reranker, LLM_ai, Redis
Concepts (Dico), Activations (Activation), Requête
Shortlist → Logs
Runtime only


activation
Verticale
5
Index activations
PostgreSQL
Concepts (Dico)
Activations → Matching
Index only


logs
Verticale
8
Tracer requêtes
PostgreSQL, metrics
Shortlist (Matching)
Feedback → Curation/Market
Logs purs


market
Verticale
9
Analyse marché
pgvector, LLM_ai
Logs, Activations
Insights
Pas SEO/matching


curation
Verticale
10
Validation humaine
Django admin, Celery, LLM_ai
Feedback (Logs)
Proposals → Dico
Pas enrichissement


language
Transverse
Tous
Traduction
Mistral API
Appels pull
Traductions
Appel pull only


seo
Transverse
9
Balises SEO
Django templates, language
Appels pull
Balises
Pas analyse


LLM_ai
Transverse
3, 6, 7, 9, 10
Enrichissement
Mistral API, Redis
Appels pull
Enrichissements
Service only


taxonomy
Transverse
1, 3
Types/hiérarchies
PostgreSQL, JSONField
Appels pull
Structures
Pas relations dynamiques


media
Transverse
1, 2
Multimédias
Django FileField, S3
Appels pull
Fichiers
Storage only


metrics
Transverse
8, 9
Stats
PostgreSQL, Grafana
Appels pull
Métriques
Collection only


permissions
Transverse
10
Accès
Django auth
Appels pull
Règles
Règles only

