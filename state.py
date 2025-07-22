

from typing import Optional, Dict, List  #typing : Fournit des outils pour l'annotation de type en Python. Optional signifie "ce champ peut être de ce type OU None", Dict pour les dictionnaires, et List pour les listes.
from typing_extensions import TypedDict # C'est un type spécial de dictionnaire où l'on peut spécifier à l'avance les clés et le type de leurs valeurs. C'est ce que LangGraph utilise pour définir son état.
from pydantic import BaseModel, Field # pydantic Une bibliothèque extrêmement puissante pour la validation de données. BaseModel est la classe de base pour créer des modèles de données, et Field permet d'ajouter des métadonnées (comme une description).

# --- Modèles de données Pydantic ---
# Définit la structure de données pour notre SOP.
# C'est la "forme" que le sop_structure_agent doit générer
# et que le validateur et le bpmn_engineer vont utiliser.

class StructuredSop(BaseModel): #Cette classe définit ce qu'est une "SOP valide" pour notre système.
    #utilisé pour la validation du sop generée par agent2
    """
    Modèle pour une Procédure Opérationnelle Standard avec une structure simplifiée.
    """
    #Nous déclarons qu'une SOP doit avoir un attribut titre, et que sa valeur doit être une chaîne de caractères (str). 
    titre: str = Field(description="Le titre clair et concis de la procédure.")
    #= Field(...) : C'est une façon d'ajouter des informations supplémentaires, principalement pour la documentation
    #C'est la partie la plus importante. Nous déclarons que l'attribut etapes doit être un dictionnaire (Dict). De plus, 
    # nous spécifions que les clés de ce dictionnaire doivent être des entiers (int) et que les valeurs associées doivent être des chaînes de caractères (str).
    etapes: Dict[int, str] = Field(
        description="Un dictionnaire des étapes, où la clé est le numéro de l'étape et la valeur est la description."
    )

class ClarificationOutput(BaseModel):
    """Schéma Pydantic pour la sortie validée de l'agent de clarification."""
    description: str = Field(
        min_length=20, 
        description="La description doit être suffisamment longue pour être utile."
    )

    def validate_content(self):
        """Méthode de validation personnalisée pour vérifier les phrases de refus courantes."""
        refusal_phrases = ["je ne peux pas", "je ne suis pas capable", "en tant que modèle de langage"]
        lower_description = self.description.lower()
        for phrase in refusal_phrases:
            if phrase in lower_description:
                # Si une phrase de refus est trouvée, on lève une ValueError,
                # ce qui sera attrapé comme une erreur de validation.
                raise ValueError(f"La description contient une phrase de refus: '{phrase}'")
        return self

class AuditResult(BaseModel):
    """Schéma Pydantic pour la réponse de l'agent auditeur."""
    is_logical: bool = Field(description="True si la SOP est logique, False sinon.")
    reason: str = Field(min_length=10, description="L'explication doit être claire et d'au moins 10 caractères.")

# --- État du Graphe ---
# C'est le "conteneur" (sac à dos partagé) de données qui circule entre tous les agents de notre graphe.
# Chaque agent peut lire et écrire dans cet état pour collaborer.

class GraphState(TypedDict):
    """
    Représente l'état global et partagé de notre graphe d'agents.
    """
    # -- Entrée initiale --
    input_question: str
    
    # -- Données générées par les agents --
    general_response: Optional[str]   # Description textuelle du processus (générée par l'agent de clarification)
    structured_sop: Optional[Dict]    # La SOP au format JSON structuré (générée par l'agent structureur)
    validation_report: Optional[Dict] # Le rapport de l'auditeur IA (généré par le validateur)
    bpmn_xml: Optional[str]           # La chaîne de caractères XML du BPMN final (générée par l'ingénieur BPMN)
    raw_llm_response_for_structuring: Optional[str]
    # -- Champs pour la logique et le contrôle --
    
    # Utilisé pour la boucle de correction intelligente entre le validateur et le structureur.
    #C'est ce que l'Agent 3 remplit pour dire à l'Agent 2 ce qu'il faut corriger. Il est None la plupart du temps.
    correction_feedback: Optional[str]
    
    # Champ clé pour le routage conditionnel : indique au graphe quel agent appeler ensuite.
    next_action: str
    
    # (Optionnel, mais utile pour le debug)
    #Un champ pour une utilisation future. On pourrait y stocker les interactions pour donner plus de contexte au LLM dans des conversations plus longues.
    conversation_history: List[str]