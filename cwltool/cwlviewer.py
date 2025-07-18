"""Visualize a CWL workflow."""

from collections.abc import Iterator
from importlib.resources import files
from typing import cast
from urllib.parse import urlparse

import pydot
import rdflib


def _get_inner_edges_query() -> str:
    return files("cwltool").joinpath("rdfqueries/get_inner_edges.sparql").read_text()


def _get_input_edges_query() -> str:
    return files("cwltool").joinpath("rdfqueries/get_input_edges.sparql").read_text()


def _get_output_edges_query() -> str:
    return files("cwltool").joinpath("rdfqueries/get_output_edges.sparql").read_text()


def _get_root_query() -> str:
    return files("cwltool").joinpath("rdfqueries/get_root.sparql").read_text()


class CWLViewer:
    """Produce similar images with the https://github.com/common-workflow-language/cwlviewer."""

    def __init__(self, rdf_description: str):
        """Create a viewer object based on the rdf description of the workflow."""
        self._dot_graph: pydot.Graph = CWLViewer._init_dot_graph()
        self._rdf_graph: rdflib.graph.Graph = self._load_cwl_graph(rdf_description)
        self._root_graph_uri: str = self._get_root_graph_uri()
        self._set_inner_edges()
        self._set_input_edges()
        self._set_output_edges()

    def _load_cwl_graph(self, rdf_description: str) -> rdflib.graph.Graph:
        rdf_graph = rdflib.Graph()
        rdf_graph.parse(data=rdf_description, format="n3")
        return rdf_graph

    def _set_inner_edges(self) -> None:
        get_inner_edges_query = _get_inner_edges_query()
        inner_edges = cast(
            Iterator[rdflib.query.ResultRow],
            self._rdf_graph.query(
                get_inner_edges_query, initBindings={"root_graph": self._root_graph_uri}
            ),
        )  # ResultRow because the query is of type SELECT
        for inner_edge_row in inner_edges:
            source_label = (
                inner_edge_row["source_label"]
                if inner_edge_row["source_label"] is not None
                else urlparse(inner_edge_row["source_step"]).fragment
            )
            # Node color and style depend on class
            source_color = (
                "#F3CEA1"
                if inner_edge_row["source_step_class"].endswith("Workflow")
                else "lightgoldenrodyellow"
            )
            source_style = (
                "dashed" if inner_edge_row["source_step_class"].endswith("Operation") else "filled"
            )
            n = pydot.Node(
                "",
                fillcolor=source_color,
                style=source_style,
                label=source_label,
                shape="record",
            )
            n.set_name(str(inner_edge_row["source_step"]))
            self._dot_graph.add_node(n)
            target_label = (
                inner_edge_row["target_label"]
                if inner_edge_row["target_label"] is not None
                else urlparse(inner_edge_row["target_step"]).fragment
            )

            target_color = (
                "#F3CEA1"
                if inner_edge_row["target_step_class"].endswith("Workflow")
                else "lightgoldenrodyellow"
            )
            target_style = (
                "dashed" if inner_edge_row["target_step_class"].endswith("Operation") else "filled"
            )
            n = pydot.Node(
                "",
                fillcolor=target_color,
                style=target_style,
                label=target_label,
                shape="record",
            )
            n.set_name(str(inner_edge_row["target_step"]))
            self._dot_graph.add_node(n)
            self._dot_graph.add_edge(
                pydot.Edge(
                    pydot.quote_id_if_necessary(str(inner_edge_row["source_step"])),
                    pydot.quote_id_if_necessary(str(inner_edge_row["target_step"])),
                )
            )

    def _set_input_edges(self) -> None:
        get_input_edges_query = _get_input_edges_query()
        inputs_subgraph = pydot.Subgraph(graph_name="cluster_inputs")
        self._dot_graph.add_subgraph(inputs_subgraph)
        inputs_subgraph.set("rank", "same")
        inputs_subgraph.set("style", "dashed")
        inputs_subgraph.set("label", "Workflow Inputs")

        input_edges = cast(
            Iterator[rdflib.query.ResultRow],
            self._rdf_graph.query(
                get_input_edges_query, initBindings={"root_graph": self._root_graph_uri}
            ),
        )  # ResultRow because the query is of type SELECT
        for input_row in input_edges:
            n = pydot.Node(
                "",
                fillcolor="#94DDF4",
                style="filled",
                label=urlparse(input_row["input"]).fragment,
                shape="record",
            )
            n.set_name(str(input_row["input"]))
            inputs_subgraph.add_node(n)
            self._dot_graph.add_edge(
                pydot.Edge(
                    pydot.quote_id_if_necessary(str(input_row["input"])),
                    pydot.quote_id_if_necessary(str(input_row["step"])),
                )
            )

    def _set_output_edges(self) -> None:
        get_output_edges = _get_output_edges_query()
        outputs_graph = pydot.Subgraph(graph_name="cluster_outputs")
        self._dot_graph.add_subgraph(outputs_graph)
        outputs_graph.set("rank", "same")
        outputs_graph.set("style", "dashed")
        outputs_graph.set("label", "Workflow Outputs")
        outputs_graph.set("labelloc", "b")
        output_edges = cast(
            Iterator[rdflib.query.ResultRow],
            self._rdf_graph.query(
                get_output_edges, initBindings={"root_graph": self._root_graph_uri}
            ),
        )  # ResultRow because the query is of type SELECT
        for output_edge_row in output_edges:
            n = pydot.Node(
                "",
                fillcolor="#94DDF4",
                style="filled",
                label=urlparse(output_edge_row["output"]).fragment,
                shape="record",
            )
            n.set_name(str(output_edge_row["output"]))
            outputs_graph.add_node(n)
            self._dot_graph.add_edge(
                pydot.Edge(
                    pydot.quote_id_if_necessary(output_edge_row["step"]),
                    pydot.quote_id_if_necessary(output_edge_row["output"]),
                )
            )

    def _get_root_graph_uri(self) -> rdflib.term.Identifier:
        get_root_query = _get_root_query()
        root = cast(
            list[rdflib.query.ResultRow],
            list(
                self._rdf_graph.query(
                    get_root_query,
                )
            ),
        )  # ResultRow because the query is of type SELECT
        if len(root) != 1:
            raise RuntimeError(
                "Cannot identify root workflow! Notice that only Workflows can be visualized"
            )

        workflow = root[0]["workflow"]
        return workflow

    @classmethod
    def _init_dot_graph(cls) -> pydot.Graph:
        graph = pydot.Graph(graph_type="digraph", simplify=False)
        graph.set("bgcolor", "#eeeeee")
        graph.set("clusterrank", "local")
        graph.set("labelloc", "bottom")
        graph.set("labelloc", "bottom")
        graph.set("labeljust", "right")

        return graph

    def get_dot_graph(self) -> pydot.Graph:
        """Get the dot graph object."""
        return self._dot_graph

    def dot(self) -> str:
        """Get the graph as graphviz."""
        return str(self._dot_graph.to_string())
