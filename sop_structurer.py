# La mission de cet agent est de prendre une description textuelle et de la transformer
# en un plan d'action structuré et formel (un graphe de processus au format JSON).

import re
import json
import time
from typing import Dict

# Imports pour le retry et la validation de données
from retry import retry
from pydantic import ValidationError

# Imports depuis vos propres modules.
# NOUVEAU : On importe maintenant ProcessGraph au lieu de StructuredSop.
from state import GraphState, ProcessGraph
from llm import TogetherModelWrapper
from dotenv import load_dotenv 
load_dotenv()
# Initialisation du LLM à l'extérieur de la fonction pour une meilleure efficacité
llm = TogetherModelWrapper(model_name="mistralai/Mixtral-8x7B-Instruct-v0.1")

# L'exception personnalisée pour la logique de retry reste la même.
class InvalidProcessGraphError(Exception):
    """Levée lorsque la sortie du LLM n'est pas un graphe de processus JSON valide."""
    pass

def extract_json_from_response(text: str) -> str:
    """Helper pour extraire le JSON d'une réponse de LLM."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return None

# La logique principale est maintenant dans une fonction décorée.
# NOUVEAU : Le décorateur écoute notre nouvelle exception.
@retry((InvalidProcessGraphError, RuntimeError), tries=3, delay=2, backoff=2)
def generate_and_validate_process_graph(prompt: str) -> Dict:
    """
    Appelle le LLM avec un prompt donné et valide la sortie avec le schéma Pydantic ProcessGraph.
    Relance automatiquement en cas d'erreur de format (InvalidProcessGraphError) ou d'API (RuntimeError).
    """
    print("   - 🌀 Tentative d'appel au LLM pour la structuration en graphe...")
    
    # 1. Appel au LLM
    raw_response = llm(prompt)
    
    # 2. Extraction du JSON
    json_string = extract_json_from_response(raw_response)
    if not json_string:
        raise InvalidProcessGraphError("Aucun bloc JSON trouvé dans la réponse du LLM.")
        
    # 3. Validation avec le schéma Pydantic ProcessGraph
    try:
        # NOUVEAU : On valide contre le schéma ProcessGraph.
        graph_model = ProcessGraph.model_validate_json(json_string)
        print("   - ✅ Structure de graphe validée par Pydantic.")
        # On retourne le dictionnaire correspondant au graphe validé.
        return graph_model.model_dump()
    except ValidationError as e:
        # Si Pydantic échoue, on lève notre erreur personnalisée pour déclencher le @retry.
        print(f"   - ⚠️ Validation Pydantic échouée : {e}. Déclenchement d'une nouvelle tentative.")
        raise InvalidProcessGraphError(e)

def sop_structure_agent(state: GraphState) -> Dict:
    """
    Agent 2: Structure la description textuelle en un ProcessGraph au format JSON.
    """
    print("\n--- AGENT 2: Structuration du Graphe de Processus (avec @retry) ---")
    
    text_to_structure = state.get("general_response")
    feedback = state.get("correction_feedback")

    if not text_to_structure:
        print("   - ❌ ERREUR: Aucune description à structurer.")
        return {"structured_sop": None, "next_action": "end_with_error"}

    # --- Étape 1 : Choisir le bon prompt en fonction du contexte ---
    prompt = ""
    if feedback:
        # La logique de correction de logique reste conceptuellement la même,
        # mais le prompt doit être adapté au nouveau format de graphe.
        print(f"   - 🔄 Mode: Correction de Logique (Feedback: '{feedback}')")
        failed_graph = state.get("structured_sop")
        failed_graph_json = json.dumps(failed_graph, indent=2, ensure_ascii=False)
        prompt = f"""
        [INST]Corrige ce graphe de processus qui a été jugé illogique.
        Raison du rejet: "{feedback}".
        Graphe incorrect: {failed_graph_json}
        Demande originale: "{text_to_structure}"
        Génère une NOUVELLE version du graphe JSON complète (titre, nodes, flows). Réponds UNIQUEMENT avec le JSON.[/INST]
        """
    else:
        # NOUVEAU : Le prompt initial est maintenant beaucoup plus puissant et demande un graphe.
        print("   - 🚀 Mode: Création Initiale du Graphe")
        prompt = f"""
        [INST]Tu es un architecte de processus expert. Ta mission est d'analyser une description textuelle et de la modéliser sous forme de graphe JSON, en identifiant les tâches, les points de décision (passerelles), et les flux qui les connectent.

        Ta sortie doit être UNIQUEMENT un objet JSON respectant le format suivant :
        - "titre": string
        - "nodes": une liste d'objets, où chaque objet a "id" (string unique), "type" ("task", "gateway", "startEvent", "endEvent"), et "label" (string).
        - "flows": une liste d'objets, où chaque objet a "source_id" (string), "target_id" (string), et optionnellement une "condition" (string).

        **Exemple :**
        Texte : "Le processus commence, on valide la demande. Si elle est ok, on la traite, sinon on la rejette. Le processus se termine."
        Sortie JSON attendue :
        ```json
        {{
          "titre": "Validation de Demande",
          "nodes": [
            {{ "id": "start", "type": "startEvent", "label": "Début" }},
            {{ "id": "task_validate", "type": "task", "label": "Valider la demande" }},
            {{ "id": "gateway_decision", "type": "gateway", "label": "Demande OK ?" }},
            {{ "id": "task_process", "type": "task", "label": "Traiter la demande" }},
            {{ "id": "task_reject", "type": "task", "label": "Rejeter la demande" }},
            {{ "id": "end", "type": "endEvent", "label": "Fin" }}
          ],
          "flows": [
            {{ "source_id": "start", "target_id": "task_validate" }},
            {{ "source_id": "task_validate", "target_id": "gateway_decision" }},
            {{ "source_id": "gateway_decision", "target_id": "task_process", "condition": "Oui" }},
            {{ "source_id": "gateway_decision", "target_id": "task_reject", "condition": "Non" }},
            {{ "source_id": "task_process", "target_id": "end" }},
            {{ "source_id": "task_reject", "target_id": "end" }}
          ]
        }}
        ```
        Texte à analyser :
        ---
        {text_to_structure}
        ---
        Réponse JSON :[/INST]
        """

    # --- Étape 2 : Appeler la fonction décorée et gérer le résultat final ---
    try:
        # La logique de boucle est gérée par le décorateur @retry.
        structured_graph = generate_and_validate_process_graph(prompt)
        
        print(f"   - ✅ Graphe de processus finalisé. Titre: '{structured_graph.get('titre')}'")
        return {
            "structured_sop": structured_graph, # On le stocke toujours dans 'structured_sop'
            "correction_feedback": None,
            "next_action": "validate_sop"
        }
    except InvalidProcessGraphError as e:
        # Si, après 3 tentatives, la fonction échoue toujours.
        print(f"   - ❌ Échec final de la structuration après plusieurs tentatives. Erreur : {e}")
        return {
            "structured_sop": None,
            "next_action": "end_with_error"
        }

# --- BLOC DE TEST UNITAIRE ---
# Le bloc de test doit être mis à jour pour refléter la nouvelle structure de sortie.
if __name__ == '__main__':
    print("--- TEST: sop_structure_agent (Mode Graphe) ---")

    test_state_initial = {
        "general_response": "Le processus de gestion des retours de produits clients commence par la réception de la demande de retour de la part du client, qui peut être effectuée via différents canaux tels qu'un appel téléphonique, un e-mail ou un formulaire de contact en ligne. Dès réception de la demande, un membre de l'équipe du service client vérifie si le produit est éligible au retour, en fonction des conditions de retour de l'entreprise.   Si le produit est éligible au retour, le client est informé des prochaines étapes et lui est demandé d'expédier le produit à l'adresse indiquée par l'entreprise. Une fois le produit reçu et inspecté par l'équipe de contrôle qualité, la décision de remboursement ou de réparation est prise.   Si le produit est en bon état et peut être revendu, l'entreprise procède au remboursement du client en créditant son compte ou en lui émettant un chèque. Dans le cas où le produit est endommagé ou ne peut pas être revendu, l'entreprise propose une réparation ou un échange au client, en fonction de la politique de retour de l'entreprise.  Si le produit n'est pas éligible au retour, le client est informé de la raison du refus et des options qui s'offrent à lui, telles que la réparation ou le remplacement du produit. Toutes les étapes du processus de gestion des retours de produits clients sont soigneusement documentées et suivies pour s'assurer que les politiques de retour sont correctement mises en œuvre et que les clients sont satisfaits du processus de retour.",
        "correction_feedback": None
    }
    result_initial = sop_structure_agent(test_state_initial)
    
    print("\n--- Résultat du Test ---")
    graph = result_initial.get("structured_sop")
    if graph:
        print(json.dumps(graph, indent=2, ensure_ascii=False))
        assert "titre" in graph and "nodes" in graph and "flows" in graph, "La structure de graphe (titre, nodes, flows) doit être présente."
        # On vérifie qu'une passerelle a bien été créée
        assert any(node['type'] == 'gateway' for node in graph['nodes']), "Une passerelle (gateway) devrait être détectée."
    else:
        print("La structuration en graphe a échoué.")

    print("\n\n✅ Tests terminés.")