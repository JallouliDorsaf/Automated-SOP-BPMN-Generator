# Fichier: agents/intelligent_validator_agent.py (Version avec @retry et Pydantic)

import json
import re
import time
from typing import Dict
from retry import retry
from pydantic import ValidationError

# Imports depuis vos propres modules
from state import GraphState, AuditResult # NOUVEAU : Import du schéma AuditResult
from llm import TogetherModelWrapper

llm = TogetherModelWrapper(model_name="mistralai/Mixtral-8x7B-Instruct-v0.1")

# NOUVEAU : Une exception personnalisée pour la logique de retry
class InvalidAuditResponseError(Exception):
    """Levée lorsque la réponse de l'auditeur IA est mal formée."""
    pass

def extract_json_from_response(text: str) -> str:
    """Helper pour extraire le JSON d'une réponse de LLM."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match: return match.group(0)
    return None

# NOUVEAU : La logique d'audit est isolée dans une fonction décorée
@retry(InvalidAuditResponseError, tries=3, delay=2)
def get_llm_audit(sop_text_representation: str) -> AuditResult:
    """
    Appelle le LLM auditeur et valide sa réponse JSON avec le schéma Pydantic.
    Relance automatiquement en cas d'InvalidAuditResponseError.
    """
    print("   - 🌀 Tentative d'audit LLM...")
    
    audit_prompt = f"""
    [INST]Vous êtes un auditeur de processus. Analysez la procédure suivante et répondez UNIQUEMENT avec un objet JSON contenant les clés "is_logical" (booléen) et "reason" (string).

    Procédure à analyser :
    ---
    {sop_text_representation}
    ---

    Votre analyse au format JSON :[/INST]
    """
    
    # 1. Appel au LLM
    response_text = llm(audit_prompt)
    
    # 2. Extraction du JSON
    json_string = extract_json_from_response(response_text)
    if not json_string:
        raise InvalidAuditResponseError("Aucun bloc JSON trouvé dans la réponse de l'auditeur.")
        
    # 3. Validation avec Pydantic
    try:
        # NOUVEAU : On utilise model_validate_json (la méthode moderne de Pydantic)
        audit_model = AuditResult.model_validate_json(json_string)
        print("   - ✅ Réponse de l'auditeur validée par Pydantic.")
        return audit_model
    except ValidationError as e:
        print(f"   - ⚠️ Réponse de l'auditeur invalide : {e}. Déclenchement d'une nouvelle tentative.")
        raise InvalidAuditResponseError(e)


def intelligent_validator_agent(state: GraphState) -> dict:
    """
    Agent 3 (Intelligent): Valide la logique de la SOP.
    Utilise une fonction décorée avec @retry pour fiabiliser la réponse de l'auditeur IA.
    """
    print("\n--- AGENT 3: Auditeur Qualité IA (avec @retry) ---")
    
    sop_dict = state.get("structured_sop")
    
    if not sop_dict or not sop_dict.get("etapes"):
        report = {"status": "FAILURE", "reason": "La SOP est manquante ou vide."}
        print("   - ❌ Échec Audit : SOP non fournie.")
        return {"validation_report": report, "next_action": "end_with_error"}

    # Préparer la représentation texte de la SOP
    sop_lines = []
    sop_lines.append(f"Titre: {sop_dict.get('titre', 'N/A')}")
    sop_lines.append("Étapes:")
    for num, desc in sorted(sop_dict.get('etapes', {}).items()):
        sop_lines.append(f"{num}. {desc}")
    sop_text_representation = "\n".join(sop_lines)
    
    # --- Étape 2 : Appeler la fonction décorée et gérer le résultat ---
    try:
        audit_result = get_llm_audit(sop_text_representation)
        
        # Le résultat est maintenant un objet Pydantic propre, on peut y accéder avec "."
        if audit_result.is_logical:
            report = {"status": "SUCCESS", "reason": audit_result.reason}
            print(f"   - ✅ Audit réussi : {audit_result.reason}")
            return {"validation_report": report, "next_action": "generate_bpmn"}
        else:
            report = {"status": "REJECTED", "reason": audit_result.reason}
            print(f"   - ❌ Échec Audit, demande de correction : {audit_result.reason}")
            return {
                "validation_report": report, 
                "correction_feedback": audit_result.reason,
                "next_action": "correct_sop"
            }
    except InvalidAuditResponseError as e:
        # Si, après 3 tentatives, l'auditeur ne donne pas de réponse valide
        report = {"status": "FAILURE", "reason": f"L'auditeur IA a échoué à répondre correctement. Erreur : {e}"}
        print(f"   - ❌ Erreur critique de l'auditeur IA après plusieurs tentatives.")
        return {"validation_report": report, "next_action": "end_with_error"}



# --- BLOC DE TEST UNITAIRE ---
if __name__ == '__main__':
    print("--- TEST: intelligent_validator_agent ---")

    # --- TEST 1 : SOP valide et logique ---
    print("\n--- Test 1: SOP Logique ---")
    test_sop_ok = {
        "titre": "Procédure de retour de produit",
        "etapes": {
            1: "Le client contacte le service client pour demander un retour.",
            2: "L'agent vérifie l'éligibilité du retour (date d'achat, état du produit).",
            3: "Si éligible, l'agent envoie une étiquette de retour prépayée au client.",
            4: "Le client renvoie le produit en utilisant l'étiquette.",
            5: "L'entrepôt réceptionne et inspecte le produit retourné.",
            6: "Si l'inspection est conforme, le service comptable procède au remboursement."
        }
    }
    result_ok = intelligent_validator_agent({"structured_sop": test_sop_ok})
    
    print("\n--- Résultat du Test 1 ---")
    print(json.dumps(result_ok, indent=2, ensure_ascii=False))
    # On s'attend à ce que l'agent approuve cette SOP
    assert result_ok.get("next_action") == "generate_bpmn", "Une SOP logique devrait être approuvée."

    # --- TEST 2 : SOP illogique (trop courte) ---
    print("\n\n--- Test 2: SOP Illogique ---")
    test_sop_ko = {
        "titre": "Remboursement client",
        "etapes": {
            1: "Rembourser le client." # Illogique car il manque toutes les étapes de vérification
        }
    }
    result_ko = intelligent_validator_agent({"structured_sop": test_sop_ko})

    print("\n--- Résultat du Test 2 ---")
    print(json.dumps(result_ko, indent=2, ensure_ascii=False))
    # On s'attend à ce que l'agent rejette cette SOP et demande une correction
    assert result_ko.get("next_action") == "correct_sop", "Une SOP illogique devrait être rejetée pour correction."
    
    print("\n\n✅ Tests terminés.")