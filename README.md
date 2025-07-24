# Automated-SOP-BPMN-Generator
L’objectif principal du projet est de concevoir et développer un système intelligent de génération automatique de procédures opérationnelles standard (SOP) à partir d’interactions en langage naturel avec un chatbot, puis de convertir ces SOP en modèles BPMN (Business Process Model and Notation) exploitables. .
✨ Fonctionnalités Principales
Conversion Langage Naturel vers BPMN : Transforme une simple phrase ou un paragraphe décrivant un processus en un fichier XML BPMN 2.0 complet et visualisable.
Architecture Multi-Agent : Le travail est décomposé en plusieurs agents spécialisés (Clarification, Structuration, Validation, Ingénierie BPMN), chacun avec une mission unique, orchestrés par LangGraph.
Modélisation de Workflows Complexes : Capable de détecter et de modéliser des points de décision, créant des diagrammes avec des passerelles (gateways) et des chemins conditionnels (Oui/Non).
Boucles d'Auto-Correction : Si un agent génère une sortie mal formatée (ex: JSON invalide) ou logiquement incomplète, le système le détecte et relance l'agent avec des instructions de correction.
Validation Hybride (Code + IA) : Le système utilise du code Python pour valider les règles logiques objectives (ex: "une passerelle doit avoir au moins deux sorties") et un LLM pour l'analyse sémantique subjective (ex: "l'ordre des étapes a-t-il du sens ?").


🏛️ Architecture du Système
Le pipeline est orchestré comme un graphe d'états où chaque nœud est un agent spécialisé. L'état (GraphState) circule entre les agents, s'enrichissant à chaque étape.

+-----------------+
| Demande Utilisateur |
| (Langage Naturel) |
+-----------------+
        |
        v
+------------------------+
| Agent 1: Clarification | --> Reformule et enrichit la demande initiale.
+------------------------+
        |
        v
+--------------------------+     <--+
| Agent 2: Structuration   |        |  (Feedback de Correction)
| (Génère le ProcessGraph) | --+    |
+--------------------------+   |    |
        |                      |    |
        v                      |    |
+--------------------------+   |    |
| Agent 3: Validation      | --+----+
| (Code + IA)              |
+--------------------------+
        | (Si Valide)
        v
+--------------------------+
| Agent 4: Ingénieur BPMN  | --> Construit le XML BPMN final avec le diagramme visuel.
+--------------------------+
        |
        v
+-----------------+
| Fichier BPMN    |
| (XML + Visuel)  |
+-----------------+

🛠️ Stack Technologique
Orchestration d'Agents : LangGraph
Modèles de Langage (LLM) : Intégration via un wrapper personnalisé (ex: TogetherAI pour Mixtral-8x7B-Instruct-v0.1).
Validation de Données : Pydantic pour définir des schémas de données stricts et fiabiliser les sorties des LLMs.
Logique de Retry : Bibliothèque retry pour rendre les appels aux LLMs résilients aux erreurs de format et d'API.
Génération XML : Bibliothèque standard xml.etree.ElementTree de Python.

⚙️ Comment ça marche ? Le Pipeline des Agents
Agent 1 : clarification_agent
Mission : Comprendre la demande initiale de l'utilisateur et la reformuler en une description narrative détaillée, en essayant d'expliciter les conditions et les différentes issues.
Robustesse : Utilise Pydantic et @retry pour s'assurer que la description générée est de haute qualité, non vide et ne contient pas de refus de la part du LLM.
Agent 2 : sop_structure_agent
Mission : Prendre la description narrative et la transformer en une structure de données ProcessGraph (un JSON avec des nodes et des flows). C'est l'agent le plus intelligent, capable de modéliser les gateways.
Robustesse : Possède une boucle d'auto-correction puissante. Si sa sortie n'est pas un JSON valide ou ne respecte pas le schéma ProcessGraph, il ré-appelle le LLM en lui montrant son erreur pour qu'il la corrige.
Agent 3 : intelligent_validator_agent
Mission : Agir comme un contrôleur qualité. Il valide la logique du graphe de processus généré.
Robustesse : Utilise une approche hybride :
Audit par Code : Vérifie d'abord des règles objectives (ex: une passerelle a-t-elle bien au moins deux sorties ?). C'est rapide et 100% fiable.
Audit par IA : Si l'audit par code réussit, il demande à un LLM de juger la cohérence sémantique (ex: l'ordre des étapes est-il sensé ?).
S'il détecte une erreur, il génère un correction_feedback pour que l'agent de structuration puisse améliorer le graphe.
Agent 4 : bpmn_engineer_agent
Mission : Prendre le ProcessGraph final et validé et le traduire en un fichier XML BPMN 2.0 standard.
Robustesse : Construit le XML de manière déterministe avec ElementTree. Il génère à la fois la partie logique (<bpmn:process>) et la partie visuelle (<bpmndi:BPMNDiagram>) avec un algorithme de mise en page qui gère les branchements, garantissant que le fichier est directement visualisable.