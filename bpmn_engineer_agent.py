# Fichier: agents/bpmn_engineer_agent.py

import xml.etree.ElementTree as ET
import uuid
from xml.sax.saxutils import escape
from typing import Dict, List, Tuple

# Assurez-vous que les imports depuis vos propres modules sont corrects
from state import GraphState, ProcessGraph

# ==============================================================================
#  FONCTION HELPER
# ==============================================================================

def create_safe_xml_id(prefix: str) -> str:
    """Génère un ID unique, sûr et lisible pour les éléments XML."""
    return f"{prefix}_{str(uuid.uuid4()).replace('-', '')}"

# ==============================================================================
#  FONCTION PRINCIPALE DE L'AGENT
# ==============================================================================

def bpmn_engineer_agent(state: GraphState) -> dict:
    """
    Agent 4: Génère un fichier XML BPMN 2.0 complet, avec une logique de mise en page
    améliorée pour gérer les branchements de workflow.
    """
    print("\n--- AGENT 4: Ingénieur BPMN (Mise en Page Améliorée) ---")
    
    graph_dict = state.get("structured_sop")
    validation_report = state.get("validation_report", {})

    if not graph_dict or validation_report.get("status") != "SUCCESS":
        print("   - ❌ Graphe de processus manquant ou non validé. Sortie.")
        return {"bpmn_xml": None}

    try:
        process_graph = ProcessGraph(**graph_dict)
        process_name_escaped = escape(process_graph.titre)

        # Configuration de l'environnement XML
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

        process_id = create_safe_xml_id("Process")
        process = ET.SubElement(root, "bpmn:process", {'id': process_id, 'isExecutable': "false", 'name': process_name_escaped})
        diagram = ET.SubElement(root, "bpmndi:BPMNDiagram", {'id': create_safe_xml_id("BPMNDiagram")})
        plane = ET.SubElement(diagram, "bpmndi:BPMNPlane", {'id': create_safe_xml_id("BPMNPlane"), 'bpmnElement': process_id})

        # --- SECTION 1 : CALCUL DE LA MISE EN PAGE (LAYOUT) ---
        coords = {}
        nodes_by_id = {node.id: node for node in process_graph.nodes}
        
        # Trouver le nœud de départ
        start_node_id = next((n.id for n in process_graph.nodes if n.type == 'startEvent'), None)
        if not start_node_id: raise ValueError("Aucun 'startEvent' trouvé dans le graphe.")
        
        # Constantes de dessin
        X_START, Y_START = 150, 250
        X_GAP, Y_GAP = 120, 120
        SIZES = { "startEvent": (36, 36), "endEvent": (36, 36), "task": (100, 80), "gateway": (50, 50) }

        # Algorithme de placement simple basé sur une traversée de graphe
        q = [(start_node_id, X_START, Y_START)]
        visited_coords = {} # Stocke les coordonnées pour éviter de recalculer
        
        while q:
            node_id, x, y = q.pop(0)
            if node_id in visited_coords: continue
            
            node = nodes_by_id[node_id]
            w, h = SIZES[node.type]
            # Ajustement Y pour un meilleur alignement
            cy = y - h // 2
            visited_coords[node_id] = {'x': x, 'y': cy, 'width': w, 'height': h}
            
            outgoing_flows = [f for f in process_graph.flows if f.source_id == node_id]
            is_gateway = node.type == 'gateway'
            
            # Calculer la position des nœuds suivants
            next_x = x + w + X_GAP
            for i, flow in enumerate(sorted(outgoing_flows, key=lambda f: f.condition or '')):
                next_y = y + (i - (len(outgoing_flows) - 1) / 2) * Y_GAP if is_gateway else y
                q.append((flow.target_id, next_x, next_y))
        
        # --- SECTION 2 : GÉNÉRATION DU XML LOGIQUE ET VISUEL ---
        
        # On génère les formes (shapes) en utilisant les coordonnées calculées
        for node_id, c in visited_coords.items():
            node = nodes_by_id[node_id]
            node_label_escaped = escape(node.label)
            
            if node.type == "startEvent": ET.SubElement(process, "bpmn:startEvent", {'id': node_id, 'name': node_label_escaped})
            elif node.type == "endEvent": ET.SubElement(process, "bpmn:endEvent", {'id': node_id, 'name': node_label_escaped})
            elif node.type == "task": ET.SubElement(process, "bpmn:userTask", {'id': node_id, 'name': node_label_escaped})
            elif node.type == "gateway": ET.SubElement(process, "bpmn:exclusiveGateway", {'id': node_id, 'name': node_label_escaped})
            
            shape = ET.SubElement(plane, "bpmndi:BPMNShape", {'id': f"{node.id}_di", 'bpmnElement': node.id})
            ET.SubElement(shape, "dc:Bounds", {k: str(int(v)) for k, v in c.items()})

        # On génère les flèches (edges)
        for flow in process_graph.flows:
            flow_id = create_safe_xml_id("Flow")
            flow_attributes = {'id': flow_id, 'sourceRef': flow.source_id, 'targetRef': flow.target_id}
            if flow.condition: flow_attributes['name'] = escape(flow.condition)
            ET.SubElement(process, "bpmn:sequenceFlow", flow_attributes)
            
            c_source, c_target = visited_coords[flow.source_id], visited_coords[flow.target_id]
            edge = ET.SubElement(plane, "bpmndi:BPMNEdge", {'id': f"{flow_id}_di", 'bpmnElement': flow_id})
            
            start_x, start_y = c_source['x'] + c_source['width'], c_source['y'] + c_source['height'] // 2
            end_x, end_y = c_target['x'], c_target['y'] + c_target['height'] // 2
            
            ET.SubElement(edge, "di:waypoint", {'x': str(start_x), 'y': str(start_y)})
            if start_y != end_y: # Si c'est une branche, on ajoute des points intermédiaires
                ET.SubElement(edge, "di:waypoint", {'x': str(start_x + X_GAP // 2), 'y': str(start_y)})
                ET.SubElement(edge, "di:waypoint", {'x': str(start_x + X_GAP // 2), 'y': str(end_y)})
            ET.SubElement(edge, "di:waypoint", {'x': str(end_x), 'y': str(end_y)})
            
        bpmn_xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
        
        print(f"   - ✅ Fichier XML BPMN complet (avec diagramme) généré pour '{process_name_escaped}'.")
        return {"bpmn_xml": bpmn_xml_string}

    except Exception as e:
        print(f"   - ❌ ERREUR critique lors de la génération du BPMN : {e}")
        import traceback
        traceback.print_exc()
        return {"bpmn_xml": None}
# ==============================================================================
#  BLOC DE TEST UNITAIRE AMÉLIORÉ
# ==============================================================================
if __name__ == '__main__':
    print("="*60)
    print("--- TEST UNITAIRE : bpmn_engineer_agent (Mode Graphe) ---")
    print("="*60)

    # --- DÉFINITION DES DONNÉES DE TEST ---

    # CAS 1 : Un graphe de processus simple avec un branchement symétrique
    GRAPH_SIMPLE = {
        "titre": "Processus de Validation Simple",
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

    # CAS 2 : Un graphe avec des branches ASYMÉTRIQUES
    # La branche "Oui" est longue (3 étapes), la branche "Non" est courte (1 étape).
    GRAPH_ASYMETRIQUE = {
        "titre": "Processus d'Approbation Complexe",
        "nodes": [
            { "id": "start_node", "type": "startEvent", "label": "Début" },
            { "id": "task_a", "type": "task", "label": "Vérifier le dossier" },
            { "id": "gateway_1", "type": "gateway", "label": "Dossier complet ?" },
            # Branche longue
            { "id": "task_b", "type": "task", "label": "Compléter le dossier" },
            { "id": "task_c", "type": "task", "label": "Obtenir signature" },
            { "id": "task_d", "type": "task", "label": "Archiver le dossier approuvé" },
            # Branche courte
            { "id": "task_e", "type": "task", "label": "Envoyer email de rejet" },
            { "id": "end_node", "type": "endEvent", "label": "Fin" }
        ],
        "flows": [
            { "source_id": "start_node", "target_id": "task_a" },
            { "source_id": "task_a", "target_id": "gateway_1" },
            # Flux de la branche longue
            { "source_id": "gateway_1", "target_id": "task_b", "condition": "Oui" },
            { "source_id": "task_b", "target_id": "task_c" },
            { "source_id": "task_c", "target_id": "task_d" },
            { "source_id": "task_d", "target_id": "end_node" },
            # Flux de la branche courte
            { "source_id": "gateway_1", "target_id": "task_e", "condition": "Non" },
            { "source_id": "task_e", "target_id": "end_node" }
        ]
    }

    # --- EXÉCUTION DES TESTS ---

    # --- Test 1 : Graphe Simple ---
    print("\n--- Test 1: Génération d'un graphe à branches SYMÉTRIQUES ---")
    state_simple = {
        "structured_sop": GRAPH_SIMPLE,
        "validation_report": {"status": "SUCCESS"}
    }
    result_simple = bpmn_engineer_agent(state_simple)
    bpmn_xml_simple = result_simple.get("bpmn_xml")
    
    if bpmn_xml_simple:
        file_name_simple = "output_test_simple.bpmn"
        with open(file_name_simple, "w", encoding="utf-8") as f:
            f.write(bpmn_xml_simple)
        print(f"✅ Fichier '{file_name_simple}' généré.")
        assert '<bpmn:exclusiveGateway' in bpmn_xml_simple
        assert '<bpmndi:BPMNShape' in bpmn_xml_simple
    else:
        print("❌ Échec de la génération pour le graphe simple.")

    # --- Test 2 : Graphe Asymétrique ---
    print("\n\n--- Test 2: Génération d'un graphe à branches ASYMÉTRIQUES ---")
    state_asym = {
        "structured_sop": GRAPH_ASYMETRIQUE,
        "validation_report": {"status": "SUCCESS"}
    }
    result_asym = bpmn_engineer_agent(state_asym)
    bpmn_xml_asym = result_asym.get("bpmn_xml")

    if bpmn_xml_asym:
        file_name_asym = "output_test_asymetrique.bpmn"
        with open(file_name_asym, "w", encoding="utf-8") as f:
            f.write(bpmn_xml_asym)
        print(f"✅ Fichier '{file_name_asym}' généré.")
        assert '<bpmn:exclusiveGateway' in bpmn_xml_asym
        assert 'Obtenir signature' in bpmn_xml_asym
        assert 'Envoyer email de rejet' in bpmn_xml_asym
    else:
        print("❌ Échec de la génération pour le graphe asymétrique.")

    print("\n\n" + "="*60)
    print("✅ Tous les tests pour l'ingénieur BPMN sont terminés.")
    print("➡️  Vous pouvez maintenant ouvrir les deux fichiers .bpmn pour comparer les visualisations.")
    print("="*60)