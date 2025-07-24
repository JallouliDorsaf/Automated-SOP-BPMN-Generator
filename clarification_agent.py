# Fichier: clarification_agent.py

# La mission de cet agent a évolué : il ne crée plus un simple résumé, mais une description
# narrative détaillée du processus. Il a pour but d'identifier les actions,
# les acteurs, et surtout les potentielles conditions ("si ceci, alors cela...")
# pour préparer le terrain à l'agent de structuration.

import time
from typing import Dict
from dotenv import load_dotenv 
# retry : Bibliothèque utilisée via un "décorateur" (@retry) pour relancer automatiquement
# une fonction si elle échoue.
from retry import retry

# ValidationError : L'erreur spécifique que Pydantic lève quand les données ne
# correspondent pas au "plan" (schéma).
from pydantic import ValidationError

# On importe les "plans" de données depuis notre fichier central state.py
from state import GraphState, ClarificationOutput
from llm import TogetherModelWrapper
load_dotenv()
# Initialisation du LLM
llm = TogetherModelWrapper(model_name="mistralai/Mixtral-8x7B-Instruct-v0.1")

# L'exception personnalisée reste ici car elle est spécifique à la logique de cet agent.
# C'est le "signal d'échec" que le décorateur @retry va écouter.
class InvalidDescriptionError(Exception):
    """Levée lorsque la description générée n'est pas valide."""
    pass

# Le décorateur @retry est placé juste au-dessus de la fonction qu'il doit surveiller.
# - InvalidDescriptionError : Il ne se déclenchera QUE si cette erreur spécifique est levée.
# - tries=3 : Il tentera au maximum 3 fois (1 essai initial + 2 re-essais).
# - delay=2 : Il attendra 2 secondes entre chaque tentative.
@retry(InvalidDescriptionError, tries=3, delay=2)
def generate_and_validate_description(question: str) -> str:
    """
    Appelle le LLM et valide la sortie en utilisant le schéma Pydantic ClarificationOutput.
    Relance automatiquement en cas d'InvalidDescriptionError.
    """
    print("   - Tentative d'appel au LLM pour clarification...")
    
    # --- MODIFICATION CLÉ : Le prompt est maintenant plus exigeant ---
    # Il demande une description narrative qui inclut les conditions et les résultats.
    prompt = f"""
    [INST]Tu es un analyste métier expert. Ta mission est de prendre la demande brute de l'utilisateur et de la transformer en une **description narrative détaillée** du processus.
    Cette description doit être un paragraphe fluide qui explique les étapes principales, les points de décision, et les différentes issues possibles.
    Ton texte servira de cahier des charges pour un autre agent IA qui devra le modéliser.

    **Exemple :**
    Demande utilisateur : "comment on fait les notes de frais ?"
    Description narrative attendue : "Le processus de gestion des notes de frais commence par la soumission des dépenses par un employé. Ensuite, un manager doit examiner la demande. **Si la note est approuvée**, elle est transmise au service comptable pour remboursement. **Dans le cas contraire**, une notification de rejet est envoyée à l'employé."

    Demande de l'utilisateur : "{question}"

    Description narrative détaillée du processus :[/INST]
    """
    
    # On appelle le LLM pour obtenir la description.
    raw_output = llm(prompt)
    description_str = str(raw_output)
    
    try:
        # On utilise le schéma importé (ClarificationOutput) pour valider la description.
        # Pydantic vérifie ici que la description n'est pas trop courte.
        validated_output = ClarificationOutput(description=description_str)
        
        # On appelle notre méthode de validation personnalisée pour vérifier le contenu.
        validated_output.validate_content()
        
        print("   - ✅ Description validée par Pydantic.")
        return validated_output.description
        
    except (ValidationError, ValueError) as e:
        # Si la validation par Pydantic ou notre méthode personnalisée échoue...
        # ...on lève notre erreur personnalisée pour que le décorateur @retry l'attrape.
        print(f"   - ⚠️ Validation échouée : {e}. Déclenchement d'une nouvelle tentative.")
        raise InvalidDescriptionError(e)

def clarification_agent(state: GraphState) -> Dict:
    """
    Agent 1: Agent de Clarification.
    Orchestre l'appel à la fonction de génération/validation et gère le résultat final.
    """
    print("\n--- AGENT 1: Clarification et Description (avec @retry) ---")
    question = state["input_question"]
    
    try:
        # On appelle simplement notre fonction décorée.
        # Toute la complexité de la boucle de retry est gérée par le décorateur.
        final_description = generate_and_validate_description(question)
        
        print("   - ✅ Description finale obtenue avec succès.")
        # On met à jour l'état avec la description et le signal pour passer à l'agent suivant.
        return {
            "general_response": final_description,
            "next_action": "structure_sop" # "structure_sop" est le nom du prochain nœud
        }
    except InvalidDescriptionError as e:
        # Si, après 3 tentatives, la fonction échoue toujours, @retry
        # relève l'exception finale, que nous attrapons ici pour terminer proprement.
        print(f"   - ❌ Échec final de la clarification après plusieurs tentatives. Erreur : {e}")
        return {
            "general_response": "Erreur : Impossible de générer une description claire.",
            "next_action": "end_with_error"
        }


# ==============================================================================
#  BLOC DE TEST UNITAIRE (INCHANGÉ, TOUJOURS PERTINENT)
# ==============================================================================
if __name__ == '__main__':
    # Ce bloc permet de tester cet agent de manière isolée.
    print("="*60)
    print("🚀 TEST UNITAIRE: clarification_agent")
    print("="*60)
    
    # 1. On simule l'état d'entrée que le graphe fournirait.
    test_state = {
        "input_question": "Comment faire pour gérer un retour produit d'un client ?",
        "conversation_history": [] # On inclut les clés requises par GraphState, même si elles sont vides.
    }
    
    # 2. On exécute la fonction principale de l'agent.
    result_state = clarification_agent(test_state)
    
    # 3. On affiche le résultat pour vérification.
    print("\n--- RÉSULTAT DU TEST ---")
    print(result_state)
    assert result_state.get("next_action") != "end_with_error", "Le test de base ne devrait pas échouer."
    print("\n✅ Test de base réussi.")
    
    