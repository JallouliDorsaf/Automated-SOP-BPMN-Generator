# La mission de cet agent est de prendre une description textuelle et
#  de la transformer en un plan d'action structuré et formel (JSON)
# Fichier: agents/sop_structure_agent.py (Version avec @retry)

import re
import json
import time
from typing import Dict
from retry import retry
from pydantic import ValidationError

# Imports depuis vos propres modules
from state import GraphState, StructuredSop
from llm import TogetherModelWrapper

llm = TogetherModelWrapper(model_name="mistralai/Mixtral-8x7B-Instruct-v0.1")

# NOUVEAU : Une exception personnalisée pour la logique de retry
class InvalidSopJsonError(Exception):
    """Levée lorsque la sortie du LLM n'est pas une SOP JSON valide."""
    pass

def extract_json_from_response(text: str) -> str:
    """Helper pour extraire le JSON d'une réponse de LLM."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return None

# NOUVEAU : La logique principale est maintenant dans une fonction décorée
@retry((InvalidSopJsonError, RuntimeError), tries=3, delay=2, backoff=2)
def generate_and_validate_sop_structure(prompt: str) -> Dict:
    """
    Appelle le LLM avec un prompt donné et valide la sortie avec Pydantic.
    Relance automatiquement si une InvalidSopJsonError (format) ou une
    RuntimeError (API) est levée.
    """
    print("   - 🌀 Tentative d'appel au LLM pour la structuration...")
    
    # 1. Appel au LLM (c'est ici que la RuntimeError peut survenir)
    raw_response = llm(prompt)
    
    # 2. Extraction du JSON
    json_string = extract_json_from_response(raw_response)
    if not json_string:
        raise InvalidSopJsonError("Aucun bloc JSON trouvé dans la réponse du LLM.")
        
    # 3. Validation avec Pydantic
    try:
        sop_model = StructuredSop.model_validate_json(json_string)
        print("   - ✅ Structure validée par Pydantic.")
        return sop_model.model_dump()
    except ValidationError as e:
        # Si Pydantic échoue, on lève notre erreur de format
        print(f"   - ⚠️ Validation Pydantic échouée : {e}. Déclenchement d'une nouvelle tentative.")
        raise InvalidSopJsonError(e)


def sop_structure_agent(state: GraphState) -> Dict:
    """
    Agent 2: Structure la description en une SOP JSON.
    Utilise la bibliothèque 'retry' pour la robustesse du formatage.
    """
    print("\n--- AGENT 2: Structuration de la SOP (avec @retry) ---")
    
    text_to_structure = state.get("general_response")
    feedback = state.get("correction_feedback")

    if not text_to_structure:
        print("   - ❌ ERREUR: Aucune description à structurer.")
        return {"structured_sop": None, "next_action": "end_with_error"}

    # --- Étape 1 : Choisir le bon prompt en fonction du contexte ---
    prompt = ""
    if feedback:
        print(f"   - 🔄 Mode: Correction de Logique (Feedback: '{feedback}')")
        failed_sop = state.get("structured_sop")
        failed_sop_json = json.dumps(failed_sop, indent=2, ensure_ascii=False)
        prompt = f"""
        [INST]Corrige cette procédure jugée incomplète.
        Raison du rejet: "{feedback}".
        Procédure incorrecte: {failed_sop_json}
        Demande originale: "{text_to_structure}"
        Génère une NOUVELLE version JSON complète. Réponds UNIQUEMENT avec le JSON.[/INST]
        """
    else:
        print("   - 🚀 Mode: Création Initiale")
        prompt = f"""
        [INST]Décompose ce processus en étapes et formate-le en JSON (clés "titre" et "etapes").
        Exemple: {{"titre": "Faire du thé", "etapes": {{"1": "Faire bouillir l'eau."}}}}
        Texte à transformer: "{text_to_structure}"
        Réponds UNIQUEMENT avec le JSON.[/INST]
        """

    # --- Étape 2 : Appeler la fonction décorée et gérer le résultat final ---
    try:
        # La logique de boucle est maintenant gérée par le décorateur @retry
        structured_sop = generate_and_validate_sop_structure(prompt)
        
        print(f"   - ✅ Structuration finale réussie. Titre: '{structured_sop.get('titre')}'")
        return {
            "structured_sop": structured_sop,
            "correction_feedback": None,
            "next_action": "validate_sop"
        }
    except InvalidSopJsonError as e:
        # Si, après 3 tentatives, la fonction échoue toujours, @retry
        # relève l'exception finale que nous attrapons ici.
        print(f"   - ❌ Échec final de la structuration après plusieurs tentatives. Erreur : {e}")
        return {
            "structured_sop": None,
            "next_action": "end_with_error"
        }

# --- BLOC DE TEST UNITAIRE ---

# --- BLOC DE TEST UNITAIRE ---
if __name__ == '__main__':
    print("--- TEST: sop_structure_agent ---")

    # --- TEST 1 : Mode Initial ---
    print("\n--- Test 1: Mode Initial ---")
    test_state_initial = {
        "general_response": "Le processus de gestion des retours de produits implique la réception de la demande du client, la vérification de l'éligibilité, l'envoi d'une étiquette de retour, la réception et l'inspection du produit, et enfin le traitement du remboursement.",
        "correction_feedback": None
    }
    result_initial = sop_structure_agent(test_state_initial)
    
    print("\n--- Résultat du Test 1 (Initial) ---")
    sop = result_initial.get("structured_sop")
    if sop:
        print(json.dumps(sop, indent=2, ensure_ascii=False))
        assert "titre" in sop and "etapes" in sop, "La structure de base (titre, etapes) doit être présente."
    else:
        print("La structuration a échoué.")
    
    # --- TEST 2 : Mode Correction ---
    print("\n\n--- Test 2: Mode Correction ---")
    test_state_correction = {
        "general_response": "Le processus de gestion des retours de produits.", # La description originale
        "structured_sop": { # La SOP qui a échoué à la validation
            "titre": "Gestion des retours", 
            "etapes": {"1": "Le client demande un retour."}
        },
        "correction_feedback": "La procédure est trop courte et manque de détails cruciaux comme l'inspection et le remboursement."
    }
    result_correction = sop_structure_agent(test_state_correction)

    print("\n--- Résultat du Test 2 (Correction) ---")
    sop_corrected = result_correction.get("structured_sop")
    if sop_corrected:
        print(json.dumps(sop_corrected, indent=2, ensure_ascii=False))
        # On vérifie que la nouvelle version est plus longue que l'ancienne
        assert len(sop_corrected.get("etapes", {})) > 1, "La SOP corrigée devrait avoir plus d'une étape."
        assert result_correction.get("correction_feedback") is None, "Le feedback doit être réinitialisé."
    else:
        print("La structuration en mode correction a échoué.")

    print("\n\n✅ Tests terminés.")
