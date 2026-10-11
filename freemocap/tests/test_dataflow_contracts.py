"""GraphDefinition contracts tested without GPU, transport, workers or video fixtures."""
import unittest
from beartype.roar import BeartypeCallHintParamViolation

from freemocap.core.pipeline.dataflow.definition import (
    InputBindingRule, DataContract, GraphConnection, PortReference, GraphDefinition, GraphNode, GraphPort, DataGranularity, compile_graph,
)
from freemocap.core.pipeline.dataflow.camera_join import CameraFrameKey, CameraFrameJoin, ProducerOutcome


def graph_fixture() -> GraphDefinition:
    camera = DataContract(kind="observations", data_granularity=DataGranularity.CAMERA_FRAME, namespace="body")
    group = DataContract(kind="observations", data_granularity=DataGranularity.GROUP_FRAME, namespace="body")
    return GraphDefinition(nodes=(
        GraphNode(id="track", operation="track", outputs=(GraphPort(name="observations", contract=camera),)),
        GraphNode(id="triangulate", operation="triangulate", inputs=(GraphPort(name="observations", contract=group),)),
        GraphNode(id="annotate", operation="annotate", inputs=(GraphPort(name="observations", contract=camera),)),
    ), edges=tuple(GraphConnection(source=PortReference(node="track", port="observations"),
                       target=PortReference(node=node, port="observations"), binding=binding)
                   for node, binding in (("triangulate", InputBindingRule.ALL_CAMERAS), ("annotate", InputBindingRule.SAME_KEY))))


class DefinitionTests(unittest.TestCase):
    def test_broadcast_and_collection_are_explicit_granularity_changes(self):
        for source_granularity, target_granularity, binding in (
            (DataGranularity.RECORDING, DataGranularity.CAMERA_FRAME, InputBindingRule.BROADCAST),
            (DataGranularity.GROUP_FRAME, DataGranularity.RECORDING, InputBindingRule.COLLECT),
        ):
            source = GraphPort(name="data", contract=DataContract(kind="data", data_granularity=source_granularity))
            target = GraphPort(name="data", contract=DataContract(kind="data", data_granularity=target_granularity))
            graph = GraphDefinition(nodes=(GraphNode(id="source", operation="load", outputs=(source,)),
                                 GraphNode(id="consumer", operation="consume", inputs=(target,))),
                          edges=(GraphConnection(source=PortReference(node="source", port="data"),
                                      target=PortReference(node="consumer", port="data"), binding=binding),))
            with self.subTest(binding=binding):
                self.assertEqual(compile_graph(graph).topological_order, ("source", "consumer"))

    def test_round_trip_preserves_executable_bindings_and_independent_sinks(self):
        graph = GraphDefinition.model_validate_json(graph_fixture().model_dump_json())
        compiled = compile_graph(graph)
        self.assertEqual(compiled.definition, graph_fixture())
        self.assertEqual(compiled.topological_order[0], "track")
        self.assertFalse(any(edge.source.node == "annotate" for edge in graph.edges))

    def test_missing_and_duplicate_bindings_fail(self):
        graph = graph_fixture()
        for edges in (graph.edges[:1], graph.edges + graph.edges[:1]):
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                compile_graph(graph.model_copy(update={"edges": edges}))

    def test_semantic_mismatch_fails_even_with_same_payload_kind(self):
        graph = graph_fixture()
        for field, value in (("namespace", "hands"), ("units", "pixels"), ("reference_frame", "aligned")):
            node = graph.nodes[1]
            port = node.inputs[0]
            port = port.model_copy(update={"contract": port.contract.model_copy(update={field: value})})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "semantics"):
                compile_graph(graph.model_copy(update={"nodes": (graph.nodes[0], node.model_copy(update={"inputs": (port,)}), graph.nodes[2])}))

    def test_wrong_granularity_and_unknown_port_fail(self):
        graph = graph_fixture()
        bad_edges = (graph.edges[0].model_copy(update={"binding": InputBindingRule.SAME_KEY}),
                     graph.edges[0].model_copy(update={"source": PortReference(node="missing", port="out")}))
        for edge in bad_edges:
            with self.subTest(edge=edge), self.assertRaises(ValueError):
                compile_graph(graph.model_copy(update={"edges": (edge, graph.edges[1])}))

    def test_cycles_and_duplicate_node_ids_fail(self):
        port = GraphPort(name="data", contract=DataContract(kind="config", data_granularity=DataGranularity.RECORDING))
        nodes = tuple(GraphNode(id=name, operation="identity", inputs=(port,), outputs=(port,)) for name in ("a", "b"))
        edges = tuple(GraphConnection(source=PortReference(node=a, port="data"), target=PortReference(node=b, port="data"),
                           binding=InputBindingRule.SAME_KEY) for a, b in (("a", "b"), ("b", "a")))
        with self.assertRaisesRegex(ValueError, "cycle"):
            compile_graph(GraphDefinition(nodes=nodes, edges=edges))
        with self.assertRaisesRegex(ValueError, "unique"):
            compile_graph(GraphDefinition(nodes=(nodes[0], nodes[0]), edges=()))


class CameraJoinTests(unittest.TestCase):
    def test_frame_ordinals_are_not_coerced_from_other_types(self):
        for frame in (True, 0.0, "0", -1):
            with self.subTest(frame=frame), self.assertRaises((ValueError, BeartypeCallHintParamViolation)):
                CameraFrameKey("attempt", "group", "camera", frame)

    def setUp(self):
        self.join = CameraFrameJoin(execution="attempt", sensor_group="group", cameras=("a", "b", "c"), frames=range(2))

    def key(self, camera, frame):
        return CameraFrameKey("attempt", "group", camera, frame)

    def test_ready_frame_does_not_require_completed_streams(self):
        self.assertIsNone(self.join.receive(self.key("c", 0)))
        self.assertIsNone(self.join.receive(self.key("a", 0)))
        keys = self.join.receive(self.key("b", 0))
        self.assertEqual(tuple(key.camera for key in keys), ("a", "b", "c"))
        self.assertFalse(self.join.complete)
        self.join.finish("c", ProducerOutcome.FAILED, execution="attempt", sensor_group="group")
        self.assertTrue(self.join.failed)
        for camera in ("a", "b"):
            self.assertIsNone(self.join.receive(self.key(camera, 1)))
            self.join.finish(camera, ProducerOutcome.SUCCEEDED, execution="attempt", sensor_group="group")
        self.assertFalse(self.join.complete)

    def test_out_of_order_arrival_joins_by_frame_not_arrival(self):
        for camera, frame in (("a", 1), ("b", 0), ("c", 1), ("a", 0)):
            self.assertIsNone(self.join.receive(self.key(camera, frame)))
        self.assertEqual(self.join.receive(self.key("b", 1))[0].frame, 1)
        self.assertEqual(self.join.receive(self.key("c", 0))[0].frame, 0)
        for camera in ("a", "b", "c"):
            self.join.finish(camera, ProducerOutcome.SUCCEEDED, execution="attempt", sensor_group="group")
        self.assertTrue(self.join.complete)

    def test_foreign_duplicate_and_after_completion_data_fail(self):
        for key in (CameraFrameKey("other", "group", "a", 0), CameraFrameKey("attempt", "other", "a", 0),
                    self.key("unknown", 0), self.key("a", 2)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.join.receive(key)
        self.join.receive(self.key("a", 0))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.join.receive(self.key("a", 0))
        self.join.finish("a", ProducerOutcome.FAILED, execution="attempt", sensor_group="group")
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.join.receive(self.key("a", 1))

    def test_success_requires_exact_coverage(self):
        with self.assertRaisesRegex(ValueError, "coverage"):
            self.join.finish("a", ProducerOutcome.SUCCEEDED, execution="attempt", sensor_group="group")
        self.assertFalse(self.join.complete)

    def test_stale_terminal_outcome_cannot_fail_this_execution(self):
        with self.assertRaisesRegex(ValueError, "Foreign"):
            self.join.finish("a", ProducerOutcome.FAILED, execution="old-attempt", sensor_group="group")
        self.assertFalse(self.join.failed)


if __name__ == "__main__":
    unittest.main()
