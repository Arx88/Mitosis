import unittest
from typing import List, Optional

# Adjust the import path based on your project structure
from agentpress.xml_tool_parser import XMLToolParser
from agentpress.tool import ToolCall

class TestXMLToolParser(unittest.TestCase):

    def setUp(self):
        self.parser = XMLToolParser()

    def assertToolCallsEqual(self, result: Optional[List[ToolCall]], expected: List[ToolCall]):
        self.assertIsNotNone(result, f"Expected tool calls, but got None. XML was likely malformed or parser had an issue.")
        self.assertEqual(len(result), len(expected), f"Expected {len(expected)} tool calls, got {len(result)}. Result: {result}")
        for i, res_call in enumerate(result):
            exp_call = expected[i]
            self.assertEqual(res_call.tool_name, exp_call.tool_name, f"Mismatch in tool_name for call {i}. Expected {exp_call.tool_name}, got {res_call.tool_name}")
            self.assertEqual(res_call.tool_kwargs, exp_call.tool_kwargs, f"Mismatch in tool_kwargs for call {i}. For tool {exp_call.tool_name}, expected {exp_call.tool_kwargs}, got {res_call.tool_kwargs}")

    def test_parse_multiple_tools_no_root(self):
        xml_string = "<shell><command>ls</command></shell><web_search><query>Python</query></web_search>"
        expected_calls = [
            ToolCall(tool_name="shell", tool_kwargs={"command": "ls"}),
            ToolCall(tool_name="web_search", tool_kwargs={"query": "Python"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_single_tool_no_root(self):
        xml_string = "<shell><command>echo \"Hola\"</command></shell>"
        expected_calls = [
            ToolCall(tool_name="shell", tool_kwargs={"command": "echo \"Hola\""})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_invoke_format_single_tool(self):
        xml_string = '<invoke name="create_file"><parameter name="file_path">test.txt</parameter><parameter name="content">Hello</parameter></invoke>'
        expected_calls = [
            ToolCall(tool_name="create_file", tool_kwargs={"file_path": "test.txt", "content": "Hello"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_invoke_format_multiple_tools(self):
        xml_string = '<invoke name="tool1"><parameter name="p1">v1</parameter></invoke><invoke name="tool2"><parameter name="p2">v2</parameter></invoke>'
        expected_calls = [
            ToolCall(tool_name="tool1", tool_kwargs={"p1": "v1"}),
            ToolCall(tool_name="tool2", tool_kwargs={"p2": "v2"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_invoke_format_with_empty_param_value(self):
        xml_string = '<invoke name="tool_empty_param"><parameter name="p1"></parameter></invoke>'
        expected_calls = [
            ToolCall(tool_name="tool_empty_param", tool_kwargs={"p1": ""})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_with_function_calls_wrapper(self):
        xml_string = "<function_calls><invoke name=\"tool_a\"><parameter name=\"arg1\">val1</parameter></invoke><shell><command>pwd</command></shell></function_calls>"
        expected_calls = [
            ToolCall(tool_name="tool_a", tool_kwargs={"arg1": "val1"}),
            ToolCall(tool_name="shell", tool_kwargs={"command": "pwd"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_with_tools_wrapper(self):
        xml_string = "<tools><shell><command>ls -l</command></shell><invoke name=\"tool_b\"><parameter name=\"arg_b\">val_b</parameter></invoke></tools>"
        expected_calls = [
            ToolCall(tool_name="shell", tool_kwargs={"command": "ls -l"}),
            ToolCall(tool_name="tool_b", tool_kwargs={"arg_b": "val_b"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_simple_tool_with_attributes(self):
        xml_string = '<read-file path="doc.txt" check="true"></read-file>'
        expected_calls = [
            ToolCall(tool_name="read-file", tool_kwargs={"path": "doc.txt", "check": "true"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_simple_tool_with_attributes_and_child_params(self):
        xml_string = '<edit-file path="src.py"><content>new code</content><mode>overwrite</mode></edit-file>'
        expected_calls = [
            ToolCall(tool_name="edit-file", tool_kwargs={"path": "src.py", "content": "new code", "mode": "overwrite"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_malformed_xml(self):
        xml_string = "<shell><command>ls</command><shell>" # Malformed
        result = self.parser.parse(xml_string)
        self.assertIsNone(result, "Parser should return None for malformed XML")

    def test_parse_empty_string(self):
        xml_string = ""
        result = self.parser.parse(xml_string)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 0, "Parser should return an empty list for an empty XML string")

    def test_tool_call_with_no_parameters_simple(self):
        xml_string = "<simple_tool></simple_tool>"
        expected_calls = [
            ToolCall(tool_name="simple_tool", tool_kwargs={})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_tool_call_with_no_parameters_invoke(self):
        xml_string = "<invoke name=\"simple_tool_invoked\"></invoke>"
        expected_calls = [
            ToolCall(tool_name="simple_tool_invoked", tool_kwargs={})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_tool_call_with_empty_parameter_value_simple(self):
        xml_string = "<tool_with_empty_param><param1></param1></tool_with_empty_param>"
        expected_calls = [
            ToolCall(tool_name="tool_with_empty_param", tool_kwargs={"param1": ""})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_tool_call_with_mixed_content_parameters_simple(self):
        xml_string = "<complex_param_tool><param_name>text <nested_tag>stuff</nested_tag> more text</param_name></complex_param_tool>"
        expected_calls = [
            ToolCall(tool_name="complex_param_tool", tool_kwargs={"param_name": "text"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_invoke_with_no_parameters_self_closing(self):
        xml_string = '<invoke name="no_param_invoke_tool" />' # Self-closing style
        expected_calls = [
            ToolCall(tool_name="no_param_invoke_tool", tool_kwargs={})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_mixed_invoke_and_simple_formats(self):
        xml_string = '<invoke name="tool_one"><parameter name="p1">val1</parameter></invoke><simple_tool><param_s>val_s</param_s></simple_tool>'
        expected_calls = [
            ToolCall(tool_name="tool_one", tool_kwargs={"p1": "val1"}),
            ToolCall(tool_name="simple_tool", tool_kwargs={"param_s": "val_s"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_deeply_nested_containers(self):
        xml_string = "<tools><function_calls><invoke name=\"deep_tool\"><parameter name=\"p\">v</parameter></invoke></function_calls></tools>"
        # The parser should flatten this due to the <dummy_root> wrapping (added by parser) and iteration logic.
        # Parser logic: if element.tag.lower() in ['function_calls', 'tools']: final_tool_elements.extend(element)
        # So, dummy_root -> tools -> function_calls -> invoke. It should correctly find 'invoke'.
        expected_calls = [
            ToolCall(tool_name="deep_tool", tool_kwargs={"p": "v"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_attributes_on_invoke_tag_are_ignored(self):
        # Attributes on <invoke> itself (other than 'name') should be ignored by current logic.
        xml_string = '<invoke name="ignored_attr_invoke" extra_attr="ignore_me"><parameter name="p1">v1</parameter></invoke>'
        expected_calls = [
            ToolCall(tool_name="ignored_attr_invoke", tool_kwargs={"p1": "v1"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

    def test_parse_attributes_on_parameter_tag_are_ignored(self):
        # Attributes on <parameter> itself (other than 'name') should be ignored.
        xml_string = '<invoke name="ignored_param_attr"><parameter name="p1" other_attr="boo">v1</parameter></invoke>'
        expected_calls = [
            ToolCall(tool_name="ignored_param_attr", tool_kwargs={"p1": "v1"})
        ]
        result = self.parser.parse(xml_string)
        self.assertToolCallsEqual(result, expected_calls)

if __name__ == '__main__':
    unittest.main()
