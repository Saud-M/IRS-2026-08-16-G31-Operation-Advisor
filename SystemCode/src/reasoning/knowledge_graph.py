"""Asset, Symptom, Hypothesis, and Action Knowledge Graph.

Built upon NetworkX DiGraph. Loads structured ontology schema and provides
efficient relational graph queries for the reasoning and planning layers.
"""

import json
import os
from typing import Dict, Any, List, Optional, Set, Tuple
import networkx as nx


class KnowledgeGraph:
    """Manages the domain knowledge graph for oil and gas production train."""

    def __init__(self, ontology_path: Optional[str] = None):
        self.graph = nx.DiGraph()
        self.ontology_path = ontology_path or os.path.join("data", "ontology", "ontology.json")
        self.load_ontology(self.ontology_path)

    def load_ontology(self, filepath: str) -> None:
        """Load and parse the JSON ontology into typed graph nodes and edges."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Ontology file not found at: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.graph.clear()

        # 1. Add Plant Node
        plant = data.get("plant", {})
        plant_id = plant.get("id", "PLANT")
        self.graph.add_node(plant_id, node_type="Plant", **plant)

        # 2. Add Assets
        for asset in data.get("assets", []):
            tag = asset["tag"]
            attrs = dict(asset)
            if "type" in attrs:
                attrs["subtype"] = attrs.pop("type")
            self.graph.add_node(tag, node_type="Asset", **attrs)
            self.graph.add_edge(plant_id, tag, relationship="contains_asset")

        # 3. Add Sensors
        for sensor in data.get("sensors", []):
            tag = sensor["tag"]
            attrs = dict(sensor)
            if "type" in attrs:
                attrs["subtype"] = attrs.pop("type")
            self.graph.add_node(tag, node_type="Sensor", **attrs)
            parent_asset = sensor.get("asset_tag")
            if parent_asset and self.graph.has_node(parent_asset):
                self.graph.add_edge(parent_asset, tag, relationship="has_sensor")

        # 4. Add Symptoms
        for sym in data.get("symptoms", []):
            sym_id = sym["id"]
            attrs = dict(sym)
            if "type" in attrs:
                attrs["subtype"] = attrs.pop("type")
            self.graph.add_node(sym_id, node_type="Symptom", **attrs)
            sensor_tag = sym.get("sensor_tag")
            if sensor_tag and self.graph.has_node(sensor_tag):
                self.graph.add_edge(sensor_tag, sym_id, relationship="monitors_symptom")

        # 5. Add Hypotheses
        for hypo in data.get("hypotheses", []):
            h_id = hypo["id"]
            attrs = dict(hypo)
            if "type" in attrs:
                attrs["subtype"] = attrs.pop("type")
            self.graph.add_node(h_id, node_type="Hypothesis", **attrs)

            # Link primary and secondary symptoms to hypothesis
            for sym_id in hypo.get("primary_symptoms", []):
                if self.graph.has_node(sym_id):
                    self.graph.add_edge(sym_id, h_id, relationship="strongly_indicates", weight=1.0)

            for sym_id in hypo.get("secondary_symptoms", []):
                if self.graph.has_node(sym_id):
                    self.graph.add_edge(sym_id, h_id, relationship="corroborates", weight=0.5)

            # Link hypothesis to affected asset
            target_asset = hypo.get("target_asset")
            if target_asset and self.graph.has_node(target_asset):
                self.graph.add_edge(h_id, target_asset, relationship="affects_asset")

        # 6. Add Diagnostic Checks
        for chk in data.get("checks", []):
            chk_id = chk["id"]
            attrs = dict(chk)
            if "type" in attrs:
                attrs["subtype"] = attrs.pop("type")
            self.graph.add_node(chk_id, node_type="Check", **attrs)

        # Link Hypotheses to Required Checks
        for hypo in data.get("hypotheses", []):
            h_id = hypo["id"]
            for chk_id in hypo.get("required_checks", []):
                if self.graph.has_node(chk_id):
                    self.graph.add_edge(h_id, chk_id, relationship="requires_check")

        # 7. Add Corrective Actions
        for act in data.get("actions", []):
            act_id = act["id"]
            attrs = dict(act)
            if "type" in attrs:
                attrs["subtype"] = attrs.pop("type")
            self.graph.add_node(act_id, node_type="Action", **attrs)

        # Link Hypotheses to Mitigating Actions
        for hypo in data.get("hypotheses", []):
            h_id = hypo["id"]
            for act_id in hypo.get("mitigations", []):
                if self.graph.has_node(act_id):
                    self.graph.add_edge(h_id, act_id, relationship="mitigated_by")

        # 8. Add Document Passages
        for doc in data.get("documents", []):
            doc_id = doc["id"]
            attrs = dict(doc)
            if "type" in attrs:
                attrs["subtype"] = attrs.pop("type")
            self.graph.add_node(doc_id, node_type="DocumentPassage", **attrs)

        # Link Hypotheses to Document Citations
        for hypo in data.get("hypotheses", []):
            h_id = hypo["id"]
            for doc_id in hypo.get("citations", []):
                if self.graph.has_node(doc_id):
                    self.graph.add_edge(h_id, doc_id, relationship="documented_in")

    def get_hypotheses_for_symptoms(self, active_symptom_ids: List[str]) -> List[Dict[str, Any]]:
        """Rank candidate hypotheses based on graph connections to active symptoms."""
        candidate_scores: Dict[str, float] = {}

        for sym_id in active_symptom_ids:
            if not self.graph.has_node(sym_id):
                continue
            for _, target, data in self.graph.out_edges(sym_id, data=True):
                if self.graph.nodes[target].get("node_type") == "Hypothesis":
                    w = data.get("weight", 0.5)
                    candidate_scores[target] = candidate_scores.get(target, 0.0) + w

        # Fetch detailed hypothesis nodes
        ranked: List[Dict[str, Any]] = []
        for h_id, score in sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True):
            node_data = dict(self.graph.nodes[h_id])
            node_data["graph_score"] = round(score, 2)
            ranked.append(node_data)

        return ranked

    def get_checks_for_hypothesis(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Retrieve diagnostic checks required to evaluate a hypothesis."""
        if not self.graph.has_node(hypothesis_id):
            return []

        checks = []
        for _, target, data in self.graph.out_edges(hypothesis_id, data=True):
            if data.get("relationship") == "requires_check":
                checks.append(dict(self.graph.nodes[target]))
        return checks

    def get_mitigations_for_hypothesis(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Retrieve valid corrective actions for a given hypothesis."""
        if not self.graph.has_node(hypothesis_id):
            return []

        actions = []
        for _, target, data in self.graph.out_edges(hypothesis_id, data=True):
            if data.get("relationship") == "mitigated_by":
                actions.append(dict(self.graph.nodes[target]))
        return actions

    def get_citations_for_hypothesis(self, hypothesis_id: str) -> List[Dict[str, Any]]:
        """Retrieve documentation passages and HAZOP citations for a hypothesis."""
        if not self.graph.has_node(hypothesis_id):
            return []

        docs = []
        for _, target, data in self.graph.out_edges(hypothesis_id, data=True):
            if data.get("relationship") == "documented_in":
                docs.append(dict(self.graph.nodes[target]))
        return docs

    def get_subgraph_for_asset(self, asset_tag: str) -> nx.DiGraph:
        """Extract localized ego-network for an asset."""
        if not self.graph.has_node(asset_tag):
            return nx.DiGraph()
        neighbors = set(nx.all_neighbors(self.graph, asset_tag)) | {asset_tag}
        return self.graph.subgraph(neighbors)

    def summary(self) -> Dict[str, Any]:
        """Return structural statistics of the knowledge graph."""
        type_counts: Dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get("node_type", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        rel_counts: Dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            r = data.get("relationship", "Unknown")
            rel_counts[r] = rel_counts.get(r, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": type_counts,
            "relationship_types": rel_counts,
        }
