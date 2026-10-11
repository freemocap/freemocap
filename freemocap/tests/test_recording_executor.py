import unittest
from threading import Event

from freemocap.core.pipeline.dataflow.definition import (
    DataContract, DataGranularity, GraphNode, GraphPort, GraphDefinition,
    GraphConnection, PortReference, InputBindingRule, compile_graph,
)
from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph


def example_graph():
    port = GraphPort(name="result", contract=DataContract(kind="example", data_granularity=DataGranularity.RECORDING))
    nodes = tuple(GraphNode(id=name, operation=name, inputs=() if name == "source" else (port,),
        outputs=(port,), execution_resource="annotation" if name == "annotation" else "compute")
        for name in ("source", "annotation", "science", "save"))
    edges = tuple(GraphConnection(source=PortReference(node=parent, port="result"),
        target=PortReference(node=child, port="result"), binding=InputBindingRule.SAME_KEY)
        for parent, child in (("source", "annotation"), ("source", "science"), ("science", "save")))
    return compile_graph(GraphDefinition(nodes=nodes, edges=edges))


class RecordingExecutorTests(unittest.TestCase):
    def test_annotation_cannot_block_science_even_with_single_compute_slot(self):
        saved = Event()
        def annotate(inputs):
            self.assertTrue(saved.wait(3), "Science was blocked by annotation")
            return inputs
        def save(inputs):
            saved.set()
            return inputs
        result = execute_recording_graph(graph=example_graph(), handlers={
            "source": lambda _: {"result": 42}, "annotation": annotate,
            "science": lambda inputs: inputs, "save": save}, resource_capacity={"compute": 1, "annotation": 1})
        self.assertTrue(result.complete, result.failures)
        self.assertEqual(result.outputs["save"]["result"], 42)

    def test_failure_blocks_only_descendants(self):
        def fail(_):
            raise ValueError("camera failed")
        result = execute_recording_graph(graph=example_graph(), handlers={
            "source": lambda _: {"result": 42}, "science": fail,
            "annotation": lambda inputs: inputs, "save": lambda inputs: self.fail("blocked sink ran")})
        self.assertIn("annotation", result.outputs)
        self.assertEqual(result.blocked["save"], ("science",))
        self.assertFalse(result.complete)

    def test_missing_handler_rejected_before_any_work(self):
        with self.assertRaises(ValueError):
            execute_recording_graph(graph=example_graph(), handlers={})

    def test_pre_cancelled_run_dispatches_nothing(self):
        result = execute_recording_graph(graph=example_graph(),
            handlers={name: lambda _: self.fail("cancelled work ran") for name in ("source", "annotation", "science", "save")},
            cancelled=lambda: True)
        self.assertTrue(result.cancelled)
        self.assertFalse(result.outputs)
