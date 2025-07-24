# Fichier: main.py

import os
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# --- 1. Imports de nos composants ---

# Importer la définition de l'état partagé et des schémas Pydantic
from state import GraphState

# Importer tous nos agents.
# Assurez-vous que les fichiers des agents sont dans le même dossier ou
# dans un dossier 'agents' avec un __init__.py.
from clarification_agent import clarification_agent
from sop_structurer import sop_structure_agent
from intelligent_validator_agent import intelligent_validator_agent
from bpmn_engineer_agent import bpmn_engineer_agent

# Charger les variables d'environnement (ex: TOGETHER_API_KEY) depuis le fichier .env
load_dotenv()

# --- 2. Construction du Graphe d'Agents ---

workflow = StateGraph(GraphState)

# Ajout des nœuds au graphe. Chaque nœud est un de nos agents.
# Les noms ("clarification", "structure_sop", etc.) sont les destinations
# que les agents peuvent spécifier dans leur 'next_action'.
workflow.add_node("clarification", clarification_agent)
workflow.add_node("structure_sop", sop_structure_agent)
workflow.add_node("validate_sop", intelligent_validator_agent)
workflow.add_node("generate_report", bpmn_engineer_agent) # L'ingénieur BPMN est la dernière étape de génération

# --- 3. Définition du Flux de Travail et du Routage ---

# Le point d'entrée de notre graphe est l'agent de clarification.
workflow.set_entry_point("clarification")

# On définit une fonction de routage générique qui se base sur la clé 'next_action'
# retournée par chaque agent. C'est le cœur de notre architecture flexible.
def route_based_on_next_action(state: GraphState) -> str:
    """
    Lit la clé 'next_action' dans l'état et route vers le nœud correspondant.
    """
    next_action = state.get("next_action")
    print(f"\n--- ROUTEUR: Action suivante déterminée par l'agent -> '{next_action}' ---")
    
    # Si l'agent demande explicitement de s'arrêter, on termine.
    if not next_action or next_action == "end_with_error":
        return END

    # Sinon, on retourne le nom du prochain nœud à exécuter.
    return next_action

# Connexions conditionnelles entre les nœuds.
# Le graphe suit les instructions ('next_action') données par chaque agent.

workflow.add_conditional_edges(
    "clarification",
    route_based_on_next_action,
    {
        "structure_sop": "structure_sop",
        END: END
    }
)

workflow.add_conditional_edges(
    "structure_sop",
    route_based_on_next_action,
    {
        "validate_sop": "validate_sop",
        END: END
    }
)

# C'est ici que la boucle de correction est définie.
workflow.add_conditional_edges(
    "validate_sop",
    route_based_on_next_action,
    {
        "generate_report": "generate_report",
        "structure_sop": "structure_sop",   # Retour en arrière pour correction
        END: END
    }
)

# L'agent 'generate_report' (bpmn_engineer) est le dernier.
# Il ne retourne pas de 'next_action', donc on le connecte directement à la fin.
workflow.add_edge("generate_report", END)


# --- 4. Compilation et Exécution ---

app = workflow.compile()

# Bloc d'exécution principal
if __name__ == "__main__":
    
    # La demande utilisateur que vous voulez traiter.
    # Essayez différentes phrases, des plus simples aux plus complexes !
    prompt_utilisateur = "Je veux une procédure pour valider une note de frais. Si elle est approuvée, elle va à la compta. Sinon, on notifie l'employé et le processus se termine."
    
    print(f"\n🚀 Lancement du processus pour la demande : \"{prompt_utilisateur}\"")
    print("=" * 60)

    # L'état initial n'a besoin que de la question.
    initial_state = { "input_question": prompt_utilisateur }
    
    # Invocation du graphe avec l'état initial.
    final_state = app.invoke(initial_state)

    print("\n" + "=" * 60)
    print("🏁 Processus terminé.")
    print("=" * 60)

    # Affichage et sauvegarde du résultat final
    bpmn_output = final_state.get('bpmn_xml')
    if bpmn_output:
        print("\n\n--- RÉSULTAT BPMN 2.0 (XML) ---")
        # On n'affiche qu'un extrait si le XML est très long
        print(bpmn_output[:1500] + "..." if len(bpmn_output) > 1500 else bpmn_output)
        
        # Sauvegarde du résultat dans un fichier
        file_name = "processus_genere_final.bpmn"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(bpmn_output)
        print(f"\n✅ Fichier BPMN sauvegardé : {file_name}")
        print(f"➡️  Vous pouvez l'ouvrir sur un outil comme https://demo.bpmn.io/ pour le visualiser.")
    else:
        print("\n\n❌ La génération du BPMN a échoué ou a été interrompue.")
        # On affiche le dernier feedback disponible pour aider au débogage
        if final_state.get("validation_report"):
             print(f"   Raison de l'arrêt : {final_state['validation_report'].get('reason')}")
        elif final_state.get("correction_feedback"):
             print(f"   Dernier feedback de correction : {final_state['correction_feedback']}")