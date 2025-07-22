# Fichier: clarification_agent.py

import time
from typing import Dict
from retry import retry
from pydantic import ValidationError

# NOUVEAU : Import de ClarificationOutput depuis le fichier central state.py
from state import GraphState, ClarificationOutput
from llm import TogetherModelWrapper

llm = TogetherModelWrapper(model_name="mistralai/Mixtral-8x7B-Instruct-v0.1")

# L'exception personnalisée reste ici car elle est spécifique à la logique de cet agent
class InvalidDescriptionError(Exception):
    """Levée lorsque la description générée n'est pas valide."""
    pass

@retry(InvalidDescriptionError, tries=3, delay=2)
def generate_and_validate_description(question: str) -> str:
    """
    Appelle le LLM et valide la sortie en utilisant le schéma Pydantic.
    Relance automatiquement en cas d'InvalidDescriptionError.
    """
    print("   - Tentative d'appel au LLM...")
    
    prompt = f"""
    [INST]Tu es un analyste métier expert. Transforme la demande suivante en une description textuelle claire du processus métier.
    Ne liste pas les étapes, mais décris l'objectif global en une ou deux phrases.

    Demande de l'utilisateur : "{question}"
    Description claire du processus :[/INST]
    """
    
    raw_output = llm(prompt)
    description_str = str(raw_output)
    
    try:
        # On utilise le schéma importé pour valider la description
        validated_output = ClarificationOutput(description=description_str)
        validated_output.validate_content()
        print("   - ✅ Description validée par Pydantic.")
        return validated_output.description
    except (ValidationError, ValueError) as e:
        # Si la validation échoue, on lève notre erreur personnalisée pour déclencher le @retry
        print(f"   - ⚠️ Validation échouée : {e}. Déclenchement d'une nouvelle tentative.")
        raise InvalidDescriptionError(e)

def clarification_agent(state: GraphState) -> Dict:
    """
    Agent 1: Agent de Clarification.
    Utilise la bibliothèque 'retry' pour la robustesse.
    """
    print("\n--- AGENT 1: Clarification et Description (avec @retry) ---")
    question = state["input_question"]
    
    try:
        final_description = generate_and_validate_description(question)
        print("   - ✅ Description finale obtenue avec succès.")
        return {
            "general_response": final_description,
            "next_action": "generate_sop"
        }
    except InvalidDescriptionError as e:
        print(f"   - ❌ Échec final de la clarification après plusieurs tentatives. Erreur : {e}")
        return {
            "general_response": "Erreur : Impossible de générer une description claire.",
            "next_action": "end_with_error"
        }


# ==============================================================================
#  BLOC DE TEST UNITAIRE
# ==============================================================================
if __name__ == '__main__':
    print("="*60)
    print("🚀 TEST UNITAIRE: clarification_agent (avec contrôle de type)")
    print("="*60)
    
    test_state = {
        "input_question": "Comment faire pour gérer un retour produit d'un client ?",
        "conversation_history": []
    }
    
    result_state = clarification_agent(test_state)
    
    print("\n--- RÉSULTAT DU TEST ---")
    print(result_state)
    
    