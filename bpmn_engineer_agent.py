# Fichier: agents/bpmn_engineer_agent.py
# Fichier: agents/bpmn_engineer_agent.py

import xml.etree.ElementTree as ET
import uuid
from xml.sax.saxutils import escape
from typing import Dict

from langgraph.graph import END

# Assurez-vous que l'import depuis votre propre module est correct
from state import GraphState

# ==============================================================================
#  FONCTION HELPER
# ==============================================================================

def create_safe_xml_id(prefix: str) -> str:
    """
    Génère un ID unique, sûr et lisible pour les éléments XML.
    Utilise un UUID pour garantir l'unicité et remplace les tirets.
    """
    return f"{prefix}_{str(uuid.uuid4()).replace('-', '')}"

# ==============================================================================
#  FONCTION PRINCIPALE DE L'AGENT
# ==============================================================================

def bpmn_engineer_agent(state: GraphState) -> dict:
    """
    Agent 4: Génère un fichier XML BPMN 2.0 complet et valide à partir d'une SOP.
    Cette version est centrée sur la robustesse et la lisibilité du code.
    """
    print("\n--- AGENT 4: Ingénieur BPMN (Version Finale) ---")
    
    sop_dict = state.get("structured_sop")
    validation_report = state.get("validation_report", {})

    # Garde-fou : on vérifie que la SOP existe et qu'elle a été validée.
    if not sop_dict or validation_report.get("status") != "SUCCESS":
        print("   - ❌ SOP manquante ou non validée. Sortie de l'agent.")
        return {"bpmn_xml": None, "next_action": "end_with_error"}

    try:
        # --- ÉTAPE 1: Préparation des données ---
        process_name_escaped = escape(sop_dict.get('titre', 'ProcessusGénéré'))
        sop_steps_dict = sop_dict.get('etapes', {})

        # --- ÉTAPE 2: Configuration de l'environnement XML ---
        ns = {
            'bpmn': "http://www.omg.org/spec/BPMN/20100524/MODEL",
            'bpmndi': "http://www.omg.org/spec/BPMN/20100524/DI",
            'dc': "http://www.omg.org/spec/DD/20100524/DC",
            'di': "http://www.omg.org/spec/DD/20100524/DI",
        }
        for prefix, uri in ns.items():
            ET.register_namespace(prefix, uri)

        root = ET.Element("bpmn:definitions", {
            'id': create_safe_xml_id("Definitions"), 
            'targetNamespace': 'http://bpmn.io/schema/bpmn',
            'xmlns:bpmn': ns['bpmn'], 'xmlns:bpmndi': ns['bpmndi'],
            'xmlns:dc': ns['dc'], 'xmlns:di': ns['di']
        })

        # --- SECTION 1 : MODÈLE LOGIQUE (le "cerveau" du processus) ---
        process_id = create_safe_xml_id("Process")
        process = ET.SubElement(root, "bpmn:process", {
            'id': process_id, 
            'isExecutable': "false", 
            'name': process_name_escaped
        })
        
        logical_elements = []
        logical_flows = []
        
        start_event = ET.SubElement(process, "bpmn:startEvent", {'id': create_safe_xml_id("StartEvent"), 'name': "Début"})
        logical_elements.append(start_event)
        
        for step_id, step_description in sorted(sop_steps_dict.items()):
            task_name_escaped = escape(step_description)
            task = ET.SubElement(process, "bpmn:userTask", {'id': create_safe_xml_id(f"Activity_{step_id}"), 'name': task_name_escaped})
            logical_elements.append(task)

        end_event = ET.SubElement(process, "bpmn:endEvent", {'id': create_safe_xml_id("EndEvent"), 'name': "Fin"})
        logical_elements.append(end_event)
        
        for i in range(len(logical_elements) - 1):
            source = logical_elements[i]
            target = logical_elements[i+1]
            flow = ET.SubElement(process, "bpmn:sequenceFlow", {
                'id': create_safe_xml_id("Flow"), 
                'sourceRef': source.get('id'), 
                'targetRef': target.get('id')
            })
            logical_flows.append(flow)

        # --- SECTION 2 : DIAGRAMME VISUEL (le "dessin" du processus) ---
        diagram = ET.SubElement(root, "bpmndi:BPMNDiagram", {'id': create_safe_xml_id("BPMNDiagram")})
        plane = ET.SubElement(diagram, "bpmndi:BPMNPlane", {'id': create_safe_xml_id("BPMNPlane"), 'bpmnElement': process_id})
        
        # Constantes pour le dessin
        START_X, START_Y = 150, 200
        EVENT_W, EVENT_H = 36, 36
        TASK_W, TASK_H = 100, 80
        HORIZONTAL_GAP = 80

        element_coords = {}
        x_pos = START_X

        # On dessine les formes (cercles, rectangles)
        for element in logical_elements:
            element_id = element.get('id')
            y_pos = START_Y
            
            if 'startEvent' in element.tag or 'endEvent' in element.tag:
                w, h = EVENT_W, EVENT_H
                y_pos += (TASK_H - EVENT_H) // 2 # Aligner verticalement
            else: # userTask
                w, h = TASK_W, TASK_H
            
            shape = ET.SubElement(plane, "bpmndi:BPMNShape", {'id': f"{element_id}_di", 'bpmnElement': element_id})
            ET.SubElement(shape, "dc:Bounds", {'x': str(x_pos), 'y': str(y_pos), 'width': str(w), 'height': str(h)})
            element_coords[element_id] = {'x': x_pos, 'y': y_pos, 'width': w, 'height': h}
            x_pos += w + HORIZONTAL_GAP

        # On dessine les flèches (connexions)
        for flow in logical_flows:
            flow_id, source_id, target_id = flow.get('id'), flow.get('sourceRef'), flow.get('targetRef')
            source_coords, target_coords = element_coords[source_id], element_coords[target_id]
            
            edge = ET.SubElement(plane, "bpmndi:BPMNEdge", {'id': f"{flow_id}_di", 'bpmnElement': flow_id})
            
            start_x, start_y = source_coords['x'] + source_coords['width'], source_coords['y'] + source_coords['height'] // 2
            end_x, end_y = target_coords['x'], target_coords['y'] + target_coords['height'] // 2
            ET.SubElement(edge, "di:waypoint", {'x': str(start_x), 'y': str(start_y)})
            ET.SubElement(edge, "di:waypoint", {'x': str(end_x), 'y': str(end_y)})
        
        # --- ÉTAPE 3: Finalisation ---
        bpmn_xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
        
        print(f"   - ✅ Fichier XML BPMN valide généré pour '{process_name_escaped}'.")
        return {"bpmn_xml": bpmn_xml_string}

    except Exception as e:
        print(f"   - ❌ ERREUR critique lors de la génération du BPMN : {e}")
        import traceback
        traceback.print_exc()
        return {"bpmn_xml": None, "next_action": "end_with_error"}

# ==============================================================================
#  BLOC DE TEST UNITAIRE
# ==============================================================================
if __name__ == '__main__':
    print("--- TEST: bpmn_engineer_agent ---")
    
    test_state = {
        "structured_sop": {
            "titre": "Processus de Test & Validation",
            "etapes": {
                "1": "Première étape de test",
                "2": "Deuxième étape <avec des symboles>",
                "3": "Troisième étape de test"
            }
        },
        "validation_report": {"status": "SUCCESS"}
    }
    
    result_state = bpmn_engineer_agent(test_state)
    
    print("\n--- Résultat du Test ---")
    bpmn_xml = result_state.get("bpmn_xml")
    
    if bpmn_xml:
        print(bpmn_xml[:1000] + "..." if len(bpmn_xml) > 1000 else bpmn_xml)
        assert "<bpmn:process" in bpmn_xml
        assert "<bpmn:userTask" in bpmn_xml
        
       
        print("\n✅ Test réussi ! Le XML BPMN a été généré et semble valide.")
    else:
        print("\n❌ Échec du test. Aucun XML n'a été généré.")