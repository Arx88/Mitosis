import asyncio
from backend.agent.tools.sb_browser_tool import SandboxBrowserTool
from unittest.mock import MagicMock, AsyncMock, patch

async def main():
    mock_thread_manager = MagicMock()
    # Configure add_message to be an AsyncMock
    mock_thread_manager.add_message = AsyncMock()
    # Configure db.client for _ensure_sandbox if it were ever not patched (good practice)
    mock_thread_manager.db = MagicMock()
    mock_thread_manager.db.client = AsyncMock()

    project_id = "test_project"
    thread_id = "test_thread"

    # Initialize the tool
    browser_tool = SandboxBrowserTool(project_id, thread_id, mock_thread_manager)

    # This is the mock sandbox instance that _ensure_sandbox (when patched) will set
    mock_sandbox_for_tool = AsyncMock()
    mock_sandbox_for_tool.id = "test_sandbox_id"
    mock_sandbox_for_tool.process = MagicMock()
    mock_sandbox_for_tool.process.execute.return_value = MagicMock(
        exit_code=0,
        result='{"success": true, "message": "Navigation successful", "url": "https://www.google.com", "title": "Google"}'
    )

    # Patch SandboxBrowserTool._ensure_sandbox directly
    # new_callable=AsyncMock is important because _ensure_sandbox is an async method
    with patch.object(SandboxBrowserTool, '_ensure_sandbox', new_callable=AsyncMock) as mock_ensure_sandbox:
        # Configure the mock _ensure_sandbox to do nothing except allow the tool to set its _sandbox
        # by assigning to the tool's _sandbox attribute if needed by the original logic,
        # or simply ensuring the tool's sandbox attribute is this mock.
        # The simplest is to have it assign the mock_sandbox_for_tool to browser_tool._sandbox
        async def side_effect():
            browser_tool._sandbox = mock_sandbox_for_tool
            return mock_sandbox_for_tool # The original method returns the sandbox

        mock_ensure_sandbox.side_effect = side_effect

        try:
            # Execute the browser_navigate_to tool
            result = await browser_tool.browser_navigate_to(url="https://www.google.com")

            # The 'output' attribute of ToolResult contains the JSON string
            if result and result.output:
                import json
                try:
                    response_data = json.loads(result.output)
                    if response_data.get("success"):
                        print(f"Test passed: Navigation successful. Result: {response_data}")
                    else:
                        print(f"Test failed: Navigation unsuccessful but got data. Result: {response_data}")
                except json.JSONDecodeError:
                    print(f"Test failed: Could not parse JSON response. Raw output: {result.output}")
            else:
                print(f"Test failed: Navigation unsuccessful or no output. Result: {result}")

        except Exception as e:
            print(f"Test failed: An error occurred - {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
