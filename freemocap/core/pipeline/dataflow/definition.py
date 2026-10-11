"""Immutable graph definitions and structural validation before execution.

Configured inputs are required. Contracts describe semantics, not Python memory
layout; adapters remain responsible for validating actual scientific payloads.
"""
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class GraphDefinitionModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DataGranularity(StrEnum):
    RECORDING = "recording"
    CAMERA_FRAME = "camera_frame"
    GROUP_FRAME = "group_frame"


class InputBindingRule(StrEnum):
    SAME_KEY = "same_key"
    BROADCAST = "broadcast"
    ALL_CAMERAS = "all_cameras"
    COLLECT = "collect"


class DataContract(GraphDefinitionModel):
    kind: str = Field(min_length=1)
    data_granularity: DataGranularity
    namespace: str | None = None
    reference_frame: str | None = None
    units: str | None = None

    def same_semantics(self, other: "DataContract") -> bool:
        return self.model_dump(exclude={"data_granularity"}) == other.model_dump(exclude={"data_granularity"})


class GraphPort(GraphDefinitionModel):
    name: str = Field(min_length=1)
    contract: DataContract


class GraphNode(GraphDefinitionModel):
    id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    execution_resource: str = "compute"
    inputs: tuple[GraphPort, ...] = ()
    outputs: tuple[GraphPort, ...] = ()


class PortReference(GraphDefinitionModel):
    node: str
    port: str


class GraphConnection(GraphDefinitionModel):
    source: PortReference
    target: PortReference
    binding: InputBindingRule


class GraphDefinition(GraphDefinitionModel):
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphConnection, ...]


class CompiledGraph(GraphDefinitionModel):
    definition: GraphDefinition
    topological_order: tuple[str, ...]


def compile_graph(graph: GraphDefinition) -> CompiledGraph:
    """Reject missing/ambiguous bindings, semantic mismatches and cycles.

    Topological order is inspection metadata, not a serial execution schedule.
    This first compiler covers structural contracts, not handler availability or
    whole-record scientific configuration validation.
    """
    nodes = {node.id: node for node in graph.nodes}
    if not nodes or len(nodes) != len(graph.nodes):
        raise ValueError("GraphDefinition requires nonempty, unique node identities")
    inputs: dict[tuple[str, str], GraphPort] = {}
    outputs: dict[tuple[str, str], GraphPort] = {}
    for node in graph.nodes:
        for ports, table in ((node.inputs, inputs), (node.outputs, outputs)):
            if len({port.name for port in ports}) != len(ports):
                raise ValueError(f"Duplicate port on {node.id}")
            table.update({(node.id, port.name): port for port in ports})
    bound: set[tuple[str, str]] = set()
    parents: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in graph.edges:
        source_key = (edge.source.node, edge.source.port)
        target_key = (edge.target.node, edge.target.port)
        if source_key not in outputs or target_key not in inputs:
            raise ValueError("GraphConnection must connect an existing output to an existing input")
        if target_key in bound:
            raise ValueError(f"Input has multiple bindings: {target_key}")
        source, target = outputs[source_key].contract, inputs[target_key].contract
        if not source.same_semantics(target):
            raise ValueError(f"Incompatible data semantics: {source_key} -> {target_key}")
        granularities = (source.data_granularity, target.data_granularity)
        valid = {
            InputBindingRule.SAME_KEY: source.data_granularity == target.data_granularity,
            InputBindingRule.BROADCAST: source.data_granularity == DataGranularity.RECORDING and target.data_granularity != DataGranularity.RECORDING,
            InputBindingRule.ALL_CAMERAS: granularities == (DataGranularity.CAMERA_FRAME, DataGranularity.GROUP_FRAME),
            InputBindingRule.COLLECT: source.data_granularity != DataGranularity.RECORDING and target.data_granularity == DataGranularity.RECORDING,
        }[edge.binding]
        if not valid:
            raise ValueError(f"Invalid {edge.binding} data granularity conversion: {granularities}")
        bound.add(target_key)
        parents[edge.target.node].add(edge.source.node)
    if bound != set(inputs):
        raise ValueError(f"Unbound required inputs: {sorted(set(inputs) - bound)}")
    order: list[str] = []
    while parents:
        ready = sorted(node for node, dependencies in parents.items() if not dependencies)
        if not ready:
            raise ValueError("GraphDefinition contains a dependency cycle")
        for node in ready:
            order.append(node)
            del parents[node]
        for dependencies in parents.values():
            dependencies.difference_update(ready)
    return CompiledGraph(definition=graph, topological_order=tuple(order))
