# typing : Fournit des outils pour l'annotation de type en Python.
# Optional signifie "ce champ peut être de ce type OU None", Dict pour les dictionnaires, et List pour les listes.
# NOUVEAU : Literal est importé pour définir un champ qui ne peut prendre que certaines valeurs textuelles spécifiques.
from typing import Optional, Dict, List, Literal

# C'est un type spécial de dictionnaire où l'on peut spécifier à l'avance les clés et le type de leurs valeurs.
# C'est ce que LangGraph utilise pour définir son état.
from typing_extensions import TypedDict

# pydantic : Une bibliothèque extrêmement puissante pour la validation de données.
# BaseModel est la classe de base pour créer des modèles de données (nos "plans").
# Field permet d'ajouter des règles de validation et de la documentation à chaque champ.
from pydantic import BaseModel, Field

# ==============================================================================
# SECTION 1 : MODÈLES DE DONNÉES PYDANTIC (LES "PLANS")
# ==============================================================================

# ------------------------------------------------------------------------------
# NOUVEAUX SCHÉMAS POUR UN PROCESSUS AVEC CONDITIONS (WORKFLOW COMPLEXE)
# ------------------------------------------------------------------------------
# Le simple dictionnaire d'étapes est remplacé par une structure de graphe pour
# pouvoir modéliser des décisions, des branches et des chemins multiples.

class ProcessNode(BaseModel):
    """
    Définit le plan pour un "nœud" unique dans notre processus.
    Un nœud peut être une action, un point de départ, de fin, ou une décision.
    """
    # Chaque nœud doit avoir un identifiant unique pour qu'on puisse le connecter aux autres.
    id: str = Field(description="Un identifiant unique pour le nœud, ex: 'task_1', 'gateway_approval'.")
    
    # Le type nous dit quelle forme dessiner sur le diagramme BPMN.
    # Literal[...] force le type à être l'une des chaînes de cette liste, ce qui évite les erreurs.
    type: Literal["task", "gateway", "startEvent", "endEvent"] = Field(description="Le type de l'élément BPMN.")
    
    # C'est le texte qui sera affiché à l'intérieur de la forme sur le diagramme.
    label: str = Field(description="Le texte affiché sur l'élément, ex: 'Valider la demande'.")

class ProcessFlow(BaseModel):
    """
    Définit le plan pour une "flèche" (un flux) qui connecte deux nœuds.
    """
    # L'ID du nœud d'où part la flèche.
    source_id: str = Field(description="L'ID du nœud de départ de la flèche.")
    
    # L'ID du nœud où arrive la flèche.
    target_id: str = Field(description="L'ID du nœud d'arrivée de la flèche.")
    
    # Champ optionnel pour les flèches qui sortent d'une décision (gateway).
    # Il peut être None si la flèche n'a pas de condition.
    condition: Optional[str] = Field(
        default=None, 
        description="Le texte sur la flèche si elle part d'une passerelle (gateway), ex: 'Oui', 'Approuvé'."
    )

class ProcessGraph(BaseModel):
    """
    Le schéma Pydantic principal qui représente l'ensemble du workflow.
    Il remplace l'ancien 'StructuredSop' car il peut décrire des processus bien plus complexes.
    C'est la nouvelle "forme" que l'agent de structuration doit générer.
    """
    # Le titre global du processus.
    titre: str = Field(description="Le titre clair et concis de la procédure.")
    
    # Une liste contenant tous les nœuds (tâches, décisions...) du processus.
    nodes: List[ProcessNode] = Field(description="La liste de toutes les tâches et points de décision.")
    
    # Une liste contenant toutes les flèches qui connectent les nœuds.
    flows: List[ProcessFlow] = Field(description="La liste de toutes les connexions (flèches) entre les nœuds.")

# ------------------------------------------------------------------------------
# SCHÉMAS POUR LES AUTRES AGENTS (INCHANGÉS)
# ------------------------------------------------------------------------------

class ClarificationOutput(BaseModel):
    """Schéma Pydantic pour la sortie validée de l'agent de clarification."""
    # Le champ 'description' doit être une chaîne de caractères...
    description: str = Field(
        min_length=20, # ...d'au moins 20 caractères pour être considérée comme utile.
        description="La description doit être suffisamment longue pour être utile."
    )

    def validate_content(self):
        """Méthode de validation personnalisée pour vérifier les phrases de refus courantes."""
        refusal_phrases = ["je ne peux pas", "je ne suis pas capable", "en tant que modèle de langage"]
        lower_description = self.description.lower()
        for phrase in refusal_phrases:
            if phrase in lower_description:
                # Si une phrase de refus est trouvée, on lève une ValueError.
                # Pydantic interprète cette erreur comme un échec de validation.
                raise ValueError(f"La description contient une phrase de refus: '{phrase}'")
        return self

class AuditResult(BaseModel):
    """Schéma Pydantic pour la réponse de l'agent auditeur."""
    # Le champ 'is_logical' doit être un booléen (True ou False).
    is_logical: bool = Field(description="True si la SOP est logique, False sinon.")
    
    # Le champ 'reason' doit être une chaîne d'au moins 10 caractères.
    reason: str = Field(min_length=10, description="L'explication doit être claire et d'au moins 10 caractères.")

# ==============================================================================
# SECTION 2 : ÉTAT DU GRAPHE LANGGRAPH
# ==============================================================================

# C'est le "conteneur" (sac à dos partagé) de données qui circule entre tous les agents de notre graphe.
# Chaque agent peut lire et écrire dans cet état pour collaborer.
class GraphState(TypedDict):
    """
    Représente l'état global et partagé de notre graphe d'agents.
    """
    # -- Entrée initiale --
    # La question brute posée par l'utilisateur.
    input_question: str
    
    # -- Données générées par les agents au fil du processus --
    # Description textuelle du processus (générée par l'agent de clarification).
    general_response: Optional[str]
    
    # La SOP au format JSON structuré (générée par l'agent structureur).
    # MODIFIÉ : Ce dictionnaire devra maintenant respecter la structure de 'ProcessGraph'.
    structured_sop: Optional[Dict]
    
    # Le rapport de l'auditeur IA (généré par le validateur).
    validation_report: Optional[Dict]
    
    # La chaîne de caractères XML du BPMN final (générée par l'ingénieur BPMN).
    bpmn_xml: Optional[str]

    # Utilisé par l'agent de structuration pour montrer au LLM sa propre erreur de format.
    raw_llm_response_for_structuring: Optional[str]
    
    # -- Champs pour la logique et le contrôle du graphe --
    # C'est ce que l'agent validateur remplit pour dire à l'agent structureur ce qu'il faut corriger.
    # Il est None la plupart du temps.
    correction_feedback: Optional[str]
    
    # Champ clé pour le routage conditionnel : indique au graphe quel agent appeler ensuite.
    next_action: str
    
    # Un champ pour une utilisation future. On pourrait y stocker les interactions
    # pour donner plus de contexte au LLM dans des conversations plus longues.
    conversation_history: List[str]