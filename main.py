# main.py

import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# --- 1. Imports de nos composants ---

# Importer la définition de l'état partagé
from state import GraphState

# Importer tous nos agents.
# Pour que cela fonctionne, assurez-vous d'avoir un fichier `agents/__init__.py`
# qui contient les imports de chaque agent.
from clarification_agent import clarification_agent
from sop_structurer import sop_structure_agent
from intelligent_validator_agent import intelligent_validator_agent
from bpmn_engineer_agent import bpmn_engineer_agent

# Charger les variables d'environnement (ex: TOGETHER_API_KEY) depuis le fichier .env
load_dotenv()

# --- 2. Construction du Graphe d'Agents ---

# Création d'une instance de StateGraph qui utilisera notre GraphState
workflow = StateGraph(GraphState)

# Ajout des nœuds au graphe. Chaque nœud est un de nos agents.
# Le premier argument est un nom unique pour le nœud, le second est la fonction de l'agent.
workflow.add_node("clarifier", clarification_agent)
workflow.add_node("structurer", sop_structure_agent)
workflow.add_node("validator", intelligent_validator_agent)
workflow.add_node("bpmn_engineer", bpmn_engineer_agent)



# --- 3. Définition du Flux de Travail et du Routage ---

# Le point d'entrée de notre graphe est l'agent de clarification.
workflow.set_entry_point("clarifier")

# Connexions entre les nœuds
# De `clarifier` à `structurer` : ce lien est toujours le même.
workflow.add_edge("clarifier", "structurer")

# Après l'agent `structurer`, le flux est simple : on passe toujours au `validator`.
# Note : C'est le `validator` qui décidera s'il faut revenir au `structurer` ou continuer.
workflow.add_edge("structurer", "validator")

# LE ROUTAGE CONDITIONNEL CLÉ
# Cette fonction est appelée APRÈS l'exécution du nœud "validator".
def decide_after_validation(state: GraphState) -> str:
    """
    Lit l'état après la validation et décide de la prochaine étape.
    """
    next_action = state.get("next_action")
    if next_action == "generate_bpmn":
        # La validation a réussi, on passe à l'ingénieur BPMN
        return "bpmn_engineer"
    elif next_action == "correct_sop":
        # La validation a échoué, on retourne au structureur pour correction
        return "structurer"
    else:
        # Cas d'erreur ou autre, on termine le graphe
        return END

# On applique cette logique de décision à la sortie du nœud "validator".
workflow.add_conditional_edges(
    "validator",
    decide_after_validation,
    {
        "bpmn_engineer": "bpmn_engineer",
        "structurer": "structurer",
        END: END
    }
)

# Après l'ingénieur BPMN, le processus est terminé.
workflow.add_edge("bpmn_engineer",END )


# --- 4. Compilation et Exécution ---

# On compile le graphe en un objet exécutable.
app = workflow.compile()


# Bloc d'exécution principal
if __name__ == "__main__":
    
    # La demande utilisateur que vous voulez traiter
    # prompt_utilisateur = "Explique-moi comment faire pour embarquer un nouvel employé."
    # prompt_utilisateur = "Comment préparer une tasse de thé parfaite ?"
    prompt_utilisateur = "Je veux créer une procédure pour gérer un retour de produit par un client."
    
    print(f"🚀 Lancement du processus pour la demande : \"{prompt_utilisateur}\"")
    print("-" * 30)

    # L'état initial doit correspondre à notre GraphState
    initial_state = {
        "input_question": prompt_utilisateur,
        "conversation_history": []
    }
    
    # Invocation du graphe avec l'état initial.
    # Le `stream()` permettrait de voir les étapes en temps réel, mais `invoke()` est plus simple.
    final_state = app.invoke(initial_state)

    print("-" * 30)
    print("🏁 Processus terminé.")

    # Affichage du résultat final
    bpmn_output = final_state.get('bpmn_xml')
    if bpmn_output:
        print("\n\n--- RÉSULTAT BPMN 2.0 (XML) ---")
        print(bpmn_output)
        
        # Sauvegarde du résultat dans un fichier
        file_name = "processus_genere.bpmn"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(bpmn_output)
        print(f"\n✅ Fichier BPMN sauvegardé : {file_name}")
        print(f"➡️  Vous pouvez l'ouvrir sur un outil comme https://demo.bpmn.io/ pour le visualiser.")
    else:
        print("\n\n❌ La génération du BPMN a échoué ou a été interrompue.")
        if final_state.get("general_response"):
            print(f"Message final : {final_state['general_response']}")
        elif final_state.get("validation_report"):
             print(f"Raison de l'arrêt : {final_state['validation_report'].get('reason')}")