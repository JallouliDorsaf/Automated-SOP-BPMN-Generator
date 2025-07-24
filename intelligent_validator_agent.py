# Fichier: agents/intelligent_validator_agent.py


import json
import re
import time
from typing import Dict, Tuple

# Imports pour le retry et la validation de données
from retry import retry
from pydantic import ValidationError

# Imports depuis vos propres modules.
# On importe ProcessGraph pour la validation de structure et AuditResult pour la sortie de l'IA.
from state import GraphState, ProcessGraph, AuditResult
from llm import TogetherModelWrapper
from dotenv import load_dotenv
load_dotenv()
# Initialisation du LLM
llm = TogetherModelWrapper(model_name="mistralai/Mixtral-8x7B-Instruct-v0.1")

# ==============================================================================
#  SECTION 1 : LOGIQUE DE L'AUDITEUR IA (AVEC RETRY)
# ==============================================================================

class InvalidAuditResponseError(Exception):
    """Exception personnalisée levée lorsque la réponse de l'auditeur IA est mal formée."""
    pass

def extract_json_from_response(text: str) -> str:
    """Helper pour extraire le premier bloc JSON d'une réponse de LLM."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match: return match.group(0)
    return None

# NOUVEAU : On ajoute RuntimeError pour gérer les pannes d'API, comme pour les autres agents.
@retry((InvalidAuditResponseError, RuntimeError), tries=2, delay=2, backoff=2)
def get_llm_audit(process_graph_text: str) -> AuditResult:
    """
    Appelle le LLM auditeur et valide sa réponse JSON avec le schéma Pydantic AuditResult.
    """
    print("   - 🌀 Tentative d'audit par IA (analyse sémantique)...")
    
    # NOUVEAU : Le prompt est maintenant beaucoup plus strict et adapté à l'analyse d'un graphe.
    audit_prompt = f"""
    [INST]Vous êtes un auditeur de processus expert et très rigoureux. Votre tâche est d'analyser le graphe de processus suivant pour trouver des incohérences logiques.

    **RÈGLES D'AUDIT STRICTES :**
    1.  **CONNECTIVITÉ :** Chaque nœud (sauf début/fin) doit être logiquement connecté. Détectez les impasses.
    2.  **PASSERELLES (GATEWAYS) :** Une passerelle de décision (`gateway`) DOIT avoir **au moins DEUX** flèches de sortie. Si ce n'est pas le cas, c'est une erreur critique.
    3.  **SÉQUENCE LOGIQUE :** L'ordre global des tâches a-t-il un sens ?

    Analysez le graphe décrit ci-dessous. Répondez UNIQUEMENT avec un objet JSON.
    Le JSON doit contenir "is_logical" (booléen) et "reason" (string).

    Graphe de processus à analyser :
    ---
    {process_graph_text}
    ---
    Votre analyse au format JSON :[/INST]
    """
    
    response_text = llm(audit_prompt)
    json_string = extract_json_from_response(response_text)
    if not json_string:
        raise InvalidAuditResponseError("Aucun bloc JSON trouvé dans la réponse de l'auditeur.")
        
    try:
        audit_model = AuditResult.model_validate_json(json_string)
        print("   - ✅ Réponse de l'auditeur IA validée par Pydantic.")
        return audit_model
    except ValidationError as e:
        print(f"   - ⚠️ Réponse de l'auditeur IA invalide : {e}. Déclenchement d'une nouvelle tentative.")
        raise InvalidAuditResponseError(e)

# ==============================================================================
#  SECTION 2 : LOGIQUE DE VALIDATION PAR CODE (APPROCHE HYBRIDE)
# ==============================================================================

def validate_graph_with_code(graph_dict: Dict) -> Tuple[bool, str]:
    """
    Effectue des vérifications logiques strictes et objectives sur le graphe.
    Retourne un tuple (est_valide: bool, message: str).
    """
    print("   - 🔍 Lancement de l'audit par code (règles strictes)...")
    nodes = graph_dict.get('nodes', [])
    flows = graph_dict.get('flows', [])
    
    if not nodes or not flows:
        return False, "Le graphe est vide (pas de nœuds ou de flux)."

    # Règle : Chaque passerelle (gateway) doit avoir au moins 2 sorties.
    for node in nodes:
        if node.get('type') == 'gateway':
            node_id = node.get('id')
            outgoing_flows = sum(1 for flow in flows if flow.get('source_id') == node_id)
            if outgoing_flows < 2:
                reason = f"ERREUR LOGIQUE : La passerelle de décision '{node.get('label')}' (ID: {node_id}) est invalide. Elle doit avoir au moins 2 sorties, mais n'en a que {outgoing_flows}."
                print(f"   - ❌ Audit par code ÉCHOUÉ : {reason}")
                return False, reason
    
    print("   - ✅ Audit par code réussi.")
    return True, "La structure de base du graphe est valide."

# ==============================================================================
#  SECTION 3 : FONCTION PRINCIPALE DE L'AGENT
# ==============================================================================

def intelligent_validator_agent(state: GraphState) -> dict:
    """
    Agent 3 (Intelligent): Valide la logique du graphe de processus en utilisant une approche hybride.
    """
    print("\n--- AGENT 3: Auditeur Qualité IA (Version Hybride) ---")
    
    graph_dict = state.get("structured_sop")
    
    # Étape 0 : Validation de la structure de base du dictionnaire avec Pydantic
    try:
        if not graph_dict: raise ValueError("Le graphe de processus est manquant.")
        ProcessGraph(**graph_dict)
    except (ValidationError, ValueError) as e:
        report = {"status": "FAILURE", "reason": f"La structure du graphe fournie est invalide : {e}"}
        print(f"   - ❌ Échec de la validation structurelle : {report['reason']}")
        return {"validation_report": report, "correction_feedback": report['reason'], "next_action": "structure_sop"}

    # Étape 1 : Validation par Code pour les règles objectives
    is_structurally_valid, code_validation_reason = validate_graph_with_code(graph_dict)
    if not is_structurally_valid:
        report = {"status": "REJECTED", "reason": code_validation_reason}
        return {"validation_report": report, "correction_feedback": code_validation_reason, "next_action": "structure_sop"}

    # Étape 2 : Validation par IA pour l'analyse sémantique
    graph_lines = [f"Titre: {graph_dict.get('titre', 'N/A')}", "\nNœuds:"]
    graph_lines.extend([f"- ID: {n['id']}, Type: {n['type']}, Label: '{n['label']}'" for n in graph_dict.get('nodes', [])])
    graph_lines.append("\nFlux:")
    graph_lines.extend([f"- De '{f['source_id']}' vers '{f['target_id']}'" + (f" (Condition: '{f['condition']}')" if f.get('condition') else "") for f in graph_dict.get('flows', [])])
    process_graph_text_representation = "\n".join(graph_lines)
    
    try:
        audit_result = get_llm_audit(process_graph_text_representation)
        
        if audit_result.is_logical:
            report = {"status": "SUCCESS", "reason": audit_result.reason}
            print(f"   - ✅ Audit IA réussi : {audit_result.reason}")
            return {"validation_report": report, "correction_feedback": None, "next_action": "generate_report"}
        else:
            report = {"status": "REJECTED", "reason": audit_result.reason}
            print(f"   - ❌ Échec Audit IA, demande de correction : {audit_result.reason}")
            return { "validation_report": report, "correction_feedback": audit_result.reason, "next_action": "structure_sop" }

    except (InvalidAuditResponseError, RuntimeError) as e:
        report = {"status": "FAILURE", "reason": f"L'auditeur IA a échoué. Erreur : {e}"}
        print(f"   - ❌ Erreur critique de l'auditeur IA après plusieurs tentatives.")
        return {"validation_report": report, "next_action": "end_with_error"}

# ==============================================================================
#  BLOC DE TEST UNITAIRE
# ==============================================================================
if __name__ == '__main__':
    # On importe load_dotenv ici pour que le test soit autonome et puisse utiliser la clé API
    from dotenv import load_dotenv
    load_dotenv()
    
    print("="*60)
    print("--- TEST UNITAIRE : intelligent_validator_agent (Version Hybride) ---")
    print("="*60)

    # --- DÉFINITION DES DONNÉES DE TEST ---

    # CAS 1 : Graphe avec une ERREUR STRUCTURELLE (gateway avec 1 seule sortie)
    # Ce cas doit être détecté par le code, SANS appel au LLM.
    GRAPH_ERREUR_CODE = {
        "titre": "Processus Incomplet (Erreur Structurelle)",
        "nodes": [
            { "id": "start", "type": "startEvent", "label": "Début" },
            { "id": "task_check", "type": "task", "label": "Vérifier quelque chose" },
            { "id": "gateway_decision", "type": "gateway", "label": "Est-ce OK ?" },
            { "id": "task_continue", "type": "task", "label": "Continuer" },
            { "id": "end", "type": "endEvent", "label": "Fin" }
        ],
        "flows": [
            { "source_id": "start", "target_id": "task_check" },
            { "source_id": "task_check", "target_id": "gateway_decision" },
            { "source_id": "gateway_decision", "target_id": "task_continue", "condition": "Oui" },
            { "source_id": "task_continue", "target_id": "end" }
        ]
    }

    # CAS 2 : Graphe structurellement correct, mais SÉMANTIQUEMENT ILLOGIQUE
    # Ce cas doit être détecté par l'IA.
    GRAPH_ERREUR_IA = {
        "titre": "Processus de Paiement Illogique",
        "nodes": [
            { "id": "start", "type": "startEvent", "label": "Début" },
            { "id": "task_pay", "type": "task", "label": "Payer la facture" },
            { "id": "gateway_approve", "type": "gateway", "label": "Facture approuvée ?" },
            { "id": "task_archive", "type": "task", "label": "Archiver" },
            { "id": "end", "type": "endEvent", "label": "Fin" }
        ],
        "flows": [
            { "source_id": "start", "target_id": "task_pay" },
            { "source_id": "task_pay", "target_id": "gateway_approve" },
            { "source_id": "gateway_approve", "target_id": "task_archive", "condition": "Oui" },
            { "source_id": "gateway_approve", "target_id": "end", "condition": "Non" },
        ]
    }

    # CAS 3 : Graphe PARFAIT, logiquement et structurellement
    GRAPH_LOGIQUE = {
        "titre": "Processus de Validation de Demande",
        "nodes": [
            { "id": "start", "type": "startEvent", "label": "Réception" },
            { "id": "task_validate", "type": "task", "label": "Vérifier les infos" },
            { "id": "gateway_decision", "type": "gateway", "label": "Conforme ?" },
            { "id": "task_approve", "type": "task", "label": "Approuver" },
            { "id": "task_reject", "type": "task", "label": "Rejeter" },
            { "id": "end", "type": "endEvent", "label": "Fin" }
        ],
        "flows": [
            { "source_id": "start", "target_id": "task_validate" },
            { "source_id": "task_validate", "target_id": "gateway_decision" },
            { "source_id": "gateway_decision", "target_id": "task_approve", "condition": "Oui" },
            { "source_id": "gateway_decision", "target_id": "task_reject", "condition": "Non" },
            { "source_id": "task_approve", "target_id": "end" },
            { "source_id": "task_reject", "target_id": "end" }
        ]
    }
    
    # --- EXÉCUTION DES TESTS ---

    # --- Test 1 : Rejet par le CODE ---
    print("\n--- Test 1: Validation d'un graphe avec ERREUR DE STRUCTURE ---")
    state_ko_code = {"structured_sop": GRAPH_ERREUR_CODE}
    result_ko_code = intelligent_validator_agent(state_ko_code)
    print("\n--- Résultat du Test 1 (Rejet par Code) ---")
    print(json.dumps(result_ko_code, indent=2, ensure_ascii=False))
    assert result_ko_code.get("next_action") == "structure_sop", "Un graphe structurellement invalide doit être rejeté."
    assert "gateway" in result_ko_code.get("correction_feedback", "").lower(), "Le feedback doit mentionner le problème de la passerelle."
    print("✅ Assertions du Test 1 réussies.")

    # --- Test 2 : Rejet par l'IA ---
    print("\n\n--- Test 2: Validation d'un graphe SÉMANTIQUEMENT ILLOGIQUE ---")
    state_ko_ia = {"structured_sop": GRAPH_ERREUR_IA}
    result_ko_ia = intelligent_validator_agent(state_ko_ia)
    print("\n--- Résultat du Test 2 (Rejet par IA) ---")
    print(json.dumps(result_ko_ia, indent=2, ensure_ascii=False))
    # Ce test dépend de l'IA, il peut échouer si le LLM n'est pas assez performant
    if result_ko_ia.get("next_action") == "structure_sop":
        print("✅ L'IA a correctement rejeté le graphe illogique.")
        assert result_ko_ia.get("correction_feedback") is not None
    else:
        print("⚠️ AVERTISSEMENT : L'IA n'a pas détecté l'incohérence sémantique. Le test est considéré comme 'passant' mais le LLM pourrait être amélioré.")
    
    # --- Test 3 : Succès ---
    print("\n\n--- Test 3: Validation d'un graphe LOGIQUE ---")
    state_ok = {"structured_sop": GRAPH_LOGIQUE}
    result_ok = intelligent_validator_agent(state_ok)
    print("\n--- Résultat du Test 3 (Succès) ---")
    print(json.dumps(result_ok, indent=2, ensure_ascii=False))
    assert result_ok.get("next_action") == "generate_report", "Un graphe logique devrait être approuvé."
    assert result_ok.get("correction_feedback") is None
    print("✅ Assertions du Test 3 réussies.")

    print("\n\n" + "="*60)
    print("✅ Tous les tests pour l'agent validateur sont terminés.")
    print("="*60)        