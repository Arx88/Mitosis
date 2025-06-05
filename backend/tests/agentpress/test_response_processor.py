import asyncio
import unittest
from unittest.mock import MagicMock, patch # Ensure patch is imported if used, though not for the primary test case here.

from agentpress.response_processor import ResponseProcessor # ToolExecutionContext not directly used in this test
from agentpress.tool_registry import ToolRegistry
from agentpress.tool import Tool, ToolResult, Schema, SchemaType, XMLSchema # XMLSchema needed for MockTool
from typing import Dict, List # Required for type hints in MockTool

# Define a simple mock tool for testing
class MockTool(Tool):
    def __init__(self):
        super().__init__()
        self.my_tool_action_called_with_args = None
        self.another_action_called = False

    def get_schemas(self) -> Dict[str, List[Schema]]:
        return {
            "my_tool_action": [ # Python method name (underscored)
                Schema(
                    schema_type=SchemaType.XML,
                    xml_schema=XMLSchema(
                        tag_name="my-tool-action", # Hyphenated XML tag
                        description="A mock tool action.",
                        mappings=[]
                    )
                ),
                Schema(
                    schema_type=SchemaType.OPENAPI,
                    schema={
                        "name": "my_tool_action", # Underscored for OpenAPI direct registration
                        "description": "A mock tool action.",
                        "parameters": {"type": "object", "properties": {}}
                    }
                )
            ],
            "another_action_no_hyphen": [
                Schema(
                    schema_type=SchemaType.OPENAPI,
                    schema={
                        "name": "another_action_no_hyphen",
                        "description": "Another action.",
                        "parameters": {"type": "object", "properties": {}}
                    }
                )
            ]
        }

    async def my_tool_action(self, **kwargs): # Python method name (underscored)
        self.my_tool_action_called_with_args = kwargs
        return ToolResult(success=True, output="my_tool_action_executed")

    async def another_action_no_hyphen(self, **kwargs):
        self.another_action_called = True
        return ToolResult(success=True, output="another_action_executed")

class TestResponseProcessor(unittest.TestCase):

    def setUp(self):
        self.tool_registry = ToolRegistry()
        # Register MockTool class. The registry will create an instance.
        self.tool_registry.register_tool(MockTool)

        # Retrieve the instance of MockTool that the registry created.
        # 'my_tool_action' is the Python function name (key in registry.tools).
        self.mock_tool_instance = self.tool_registry.tools['my_tool_action']['instance']

        self.mock_add_message = MagicMock(return_value=asyncio.Future())
        self.mock_add_message.return_value.set_result(None)

        self.mock_trace = MagicMock()
        # Ensure the span mock can be used as a context manager
        mock_span_context = MagicMock()
        mock_span_context.__enter__.return_value = None
        mock_span_context.__exit__.return_value = None
        self.mock_trace.span.return_value = mock_span_context
        self.mock_trace.event = MagicMock()

        self.processor = ResponseProcessor(
            tool_registry=self.tool_registry,
            add_message_callback=self.mock_add_message,
            trace=self.mock_trace
        )

    def test_execute_tool_with_hyphenated_name_normalized(self):
        # This test verifies that calling a tool via its hyphenated alias (e.g., 'my-tool-action')
        # correctly executes the Python method 'my_tool_action' due to normalization.
        tool_call_hyphenated = {
            "function_name": "my-tool-action", # Hyphenated name, as if from XML tag or direct call
            "arguments": {"param1": "value1"}
        }

        # Run the _execute_tool method (which contains the normalization logic)
        result = asyncio.run(self.processor._execute_tool(tool_call_hyphenated))

        # Assertions
        self.assertTrue(result.success)
        self.assertEqual(result.output, "my_tool_action_executed")
        # Check that the mock tool's method was called with correct arguments
        self.assertIsNotNone(self.mock_tool_instance.my_tool_action_called_with_args)
        self.assertEqual(self.mock_tool_instance.my_tool_action_called_with_args, {"param1": "value1"})

        self.mock_trace.span.assert_called_once()

    def test_execute_tool_with_underscored_name(self):
        # This tests direct execution of a tool using its Pythonic (underscored) name.
        tool_call_underscored = {
            "function_name": "another_action_no_hyphen",
            "arguments": {"argA": "valA"}
        }

        result = asyncio.run(self.processor._execute_tool(tool_call_underscored))

        self.assertTrue(result.success)
        self.assertEqual(result.output, "another_action_executed")
        self.assertTrue(self.mock_tool_instance.another_action_called)

    def test_execute_non_existent_tool(self):
        # Tests that a non-existent tool (even after normalization) fails gracefully.
        tool_call_non_existent = {
            "function_name": "non-existent-tool",
            "arguments": {}
        }

        result = asyncio.run(self.processor._execute_tool(tool_call_non_existent))

        self.assertFalse(result.success)
        # The error message in _execute_tool includes both original and normalized names.
        self.assertIn("Tool function 'non-existent-tool' (normalized to 'non_existent_tool') not found", result.output)

if __name__ == '__main__':
    unittest.main()
