import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from backend.agentpress.tool import ToolResult # Adjusted import
from backend.agentpress.thread_manager import ThreadManager # Adjusted import
from backend.agent.tools.sb_browser_tool import SandboxBrowserTool

# Mock for the process execution result
class MockProcessExecutionResult:
    def __init__(self, exit_code, result, stderr):
        self.exit_code = exit_code
        self.result = result
        self.stderr = stderr

class TestSandboxBrowserToolRobustJsonParsing(unittest.TestCase):

    def setUp(self):
        self.project_id = "test_project"
        self.thread_id = "test_thread"
        # Mock ThreadManager if its methods are called directly or indirectly
        self.mock_thread_manager = AsyncMock(spec=ThreadManager)
        self.browser_tool = SandboxBrowserTool(
            project_id=self.project_id,
            thread_id=self.thread_id,
            thread_manager=self.mock_thread_manager
        )
        # Mock the internal _sandbox attribute and its process.execute method
        self.mock_sandbox_internal = MagicMock()
        self.browser_tool._sandbox = self.mock_sandbox_internal # Assign mock to the internal attribute
        self.browser_tool._ensure_sandbox = AsyncMock() # Still mock _ensure_sandbox as it's awaited

        # Mock upload_base64_image as it's called in _execute_browser_action
        self.mock_upload_patcher = patch('backend.agent.tools.sb_browser_tool.upload_base64_image', AsyncMock(return_value="http://fakeurl.com/image.png"))
        self.mock_upload_image = self.mock_upload_patcher.start()

    def tearDown(self):
        self.mock_upload_patcher.stop()

    def _run_async(self, coro):
        return asyncio.run(coro)

    def test_valid_json_response(self):
        """Test with a valid JSON string."""
        mock_response_data = {"message": "Success", "content": "some content"}
        stdout_json = json.dumps(mock_response_data)
        self.mock_sandbox_internal.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=0, result=stdout_json, stderr="")
        )
        self.mock_thread_manager.add_message = AsyncMock(return_value={'message_id': 'mock_message_id'})


        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertTrue(result.success)
        # Parse the JSON string in result.output
        output_data = json.loads(result.output)
        self.assertEqual(output_data["message"], "Success")
        self.browser_tool.sandbox.process.execute.assert_called_once()

    def test_invalid_json_response_malformed(self):
        """Test with a malformed JSON string (e.g., trailing comma)."""
        stdout_malformed_json = '{"message": "Success", "content": "some content",}' # Trailing comma
        self.browser_tool.sandbox.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=0, result=stdout_malformed_json, stderr="")
        )

        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertFalse(result.success)
        # For fail_response, the error message is directly in result.output
        self.assertIn("Failed to parse response JSON", result.output)
        self.assertIn(stdout_malformed_json, result.output)
        self.mock_sandbox_internal.process.execute.assert_called_once()

    def test_non_json_response_html(self):
        """Test with a non-JSON string like HTML."""
        stdout_html = "<html><body><h1>Not a JSON</h1></body></html>"
        self.browser_tool.sandbox.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=0, result=stdout_html, stderr="")
        )

        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertFalse(result.success)
        self.assertIn("Response from internal browser service was not as expected", result.output)
        self.assertIn(stdout_html, result.output)
        self.mock_sandbox_internal.process.execute.assert_called_once()

    def test_valid_json_with_leading_trailing_whitespace(self):
        """Test with valid JSON that has leading/trailing whitespace."""
        mock_response_data = {"message": "Success", "content": "whitespace test"}
        stdout_json_with_whitespace = f"   {json.dumps(mock_response_data)}   "
        self.mock_sandbox_internal.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=0, result=stdout_json_with_whitespace, stderr="")
        )
        self.mock_thread_manager.add_message = AsyncMock(return_value={'message_id': 'mock_message_id'})

        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertTrue(result.success)
        output_data = json.loads(result.output)
        self.assertEqual(output_data["message"], "Success")
        self.browser_tool.sandbox.process.execute.assert_called_once()

    def test_empty_string_response(self):
        """Test with an empty string response."""
        stdout_empty = ""
        self.browser_tool.sandbox.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=0, result=stdout_empty, stderr="")
        )

        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertFalse(result.success)
        self.assertIn("Response from internal browser service was not as expected", result.output)
        self.mock_sandbox_internal.process.execute.assert_called_once()

    def test_whitespace_only_response(self):
        """Test with a response that is only whitespace."""
        stdout_whitespace = "   \n\t   "
        self.browser_tool.sandbox.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=0, result=stdout_whitespace, stderr="")
        )

        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertFalse(result.success)
        self.assertIn("Response from internal browser service was not as expected", result.output)
        self.mock_sandbox_internal.process.execute.assert_called_once()

    def test_non_zero_exit_code(self):
        """Test when curl command returns a non-zero exit code."""
        stdout_msg = "Some error message from curl"
        stderr_msg = "Detailed error"
        self.browser_tool.sandbox.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=1, result=stdout_msg, stderr=stderr_msg)
        )

        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertFalse(result.success)
        self.assertIn("Browser automation request failed with exit code 1", result.output)
        self.assertIn(stdout_msg, result.output)
        self.assertIn(stderr_msg, result.output)
        self.mock_sandbox_internal.process.execute.assert_called_once()

    def test_json_response_with_screenshot(self):
        """Test valid JSON response that includes a screenshot."""
        mock_response_data = {
            "message": "Success with screenshot",
            "content": "some content",
            "screenshot_base64": "fake_base64_string"
        }
        stdout_json = json.dumps(mock_response_data)
        self.mock_sandbox_internal.process.execute = MagicMock(
            return_value=MockProcessExecutionResult(exit_code=0, result=stdout_json, stderr="")
        )
        self.mock_thread_manager.add_message = AsyncMock(return_value={'message_id': 'mock_message_id'})

        result = self._run_async(self.browser_tool._execute_browser_action("test_endpoint"))

        self.assertTrue(result.success)
        output_data = json.loads(result.output)
        self.assertEqual(output_data["message"], "Success with screenshot")
        self.assertEqual(output_data["image_url"], "http://fakeurl.com/image.png")
        self.mock_upload_image.assert_called_once_with("fake_base64_string")
        self.mock_sandbox_internal.process.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
