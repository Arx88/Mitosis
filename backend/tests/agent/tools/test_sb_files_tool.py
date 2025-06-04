import pytest
from unittest.mock import AsyncMock, MagicMock, call
from agentpress.tool import ToolResult
# Assuming 'backend' is in PYTHONPATH or tests are run from 'backend'
from agent.tools.sb_files_tool import SandboxFilesTool
from sandbox.sandbox import LocalDockerFileSystemWrapper # For spec

@pytest.mark.asyncio
class TestSandboxFilesTool:

    @pytest.fixture
    def mock_thread_manager(self):
        # ThreadManager might have async methods if it interacts with async DB,
        # but for these tests, its direct interactions are not critical beyond being passed.
        return MagicMock()

    @pytest.fixture
    async def files_tool(self, mock_thread_manager):
        # project_id and thread_manager are needed for SandboxFilesTool constructor
        tool = SandboxFilesTool(project_id="test_project", thread_manager=mock_thread_manager)

        # Mock _ensure_sandbox to prevent actual sandbox initialization logic
        # This method is called by each tool public method.
        tool._ensure_sandbox = AsyncMock()

        # Mock the fs object (which would be an instance of LocalDockerFileSystemWrapper)
        # and its methods. Using spec ensures that the mock adheres to the interface.
        mock_fs = AsyncMock(spec=LocalDockerFileSystemWrapper)
        mock_fs.create_folder = AsyncMock(return_value=True)
        mock_fs.upload_file = AsyncMock(return_value=True)
        mock_fs.set_file_permissions = AsyncMock(return_value=True)

        # _file_exists uses get_file_info. Mock get_file_info.
        # It should raise an exception if file not found, return info otherwise.
        mock_fs.get_file_info = AsyncMock()

        # download_file is used by str_replace, not directly by create/rewrite but good to have
        mock_fs.download_file = AsyncMock(return_value=b"file content")

        # Setup a mock sandbox object that would be set by _ensure_sandbox
        # and assign the mocked fs to it.
        # The tool methods access self.sandbox.fs and self.sandbox.get_preview_link
        tool._sandbox = AsyncMock() # Mock the _sandbox attribute directly after _ensure_sandbox is mocked
        tool._sandbox.fs = mock_fs

        # Mock get_preview_link for index.html tests
        # It's a method on the sandbox object (e.g. LocalDockerSandboxWrapper or Daytona's Sandbox)
        tool._sandbox.get_preview_link = MagicMock(return_value=MagicMock(url="http://fake.preview/index.html"))

        return tool

    # Tests for create_file
    async def test_create_file_success(self, files_tool):
        # Simulate file does not exist for _file_exists check
        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")

        result = await files_tool.create_file(file_path="new_dir/new_file.txt", file_contents="content", permissions="644")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "File 'new_dir/new_file.txt' created successfully." in result.output

        # Check that clean_path was used, so /workspace/ is prepended
        files_tool.sandbox.fs.create_folder.assert_awaited_once_with("/workspace/new_dir", "755")
        files_tool.sandbox.fs.upload_file.assert_awaited_once_with("/workspace/new_dir/new_file.txt", b"content")
        files_tool.sandbox.fs.set_file_permissions.assert_awaited_once_with("/workspace/new_dir/new_file.txt", "644")
        files_tool._ensure_sandbox.assert_awaited_once() # Ensure sandbox was checked

    async def test_create_file_no_parent_dir(self, files_tool):
        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")

        result = await files_tool.create_file(file_path="root_file.txt", file_contents="root content", permissions="600")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "File 'root_file.txt' created successfully." in result.output

        files_tool.sandbox.fs.create_folder.assert_not_awaited() # No parent dir to create
        files_tool.sandbox.fs.upload_file.assert_awaited_once_with("/workspace/root_file.txt", b"root content")
        files_tool.sandbox.fs.set_file_permissions.assert_awaited_once_with("/workspace/root_file.txt", "600")

    async def test_create_file_already_exists(self, files_tool):
        # Simulate file exists
        files_tool.sandbox.fs.get_file_info.return_value = MagicMock()

        result = await files_tool.create_file("existing_file.txt", "content") # Default permissions "644"

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "File 'existing_file.txt' already exists." in result.output
        files_tool.sandbox.fs.create_folder.assert_not_called()
        files_tool.sandbox.fs.upload_file.assert_not_called()
        files_tool.sandbox.fs.set_file_permissions.assert_not_called()

    async def test_create_file_index_html(self, files_tool):
        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")

        result = await files_tool.create_file("index.html", "html content") # Default permissions

        assert result.success is True
        assert "File 'index.html' created successfully." in result.output
        assert "[Auto-detected index.html - HTTP server available at: http://fake.preview/index.html]" in result.output
        files_tool.sandbox.fs.upload_file.assert_awaited_once_with("/workspace/index.html", b"html content")
        files_tool.sandbox.fs.set_file_permissions.assert_awaited_once_with("/workspace/index.html", "644") # Default
        files_tool.sandbox.get_preview_link.assert_called_once_with(8080)


    # Tests for full_file_rewrite
    async def test_full_file_rewrite_success(self, files_tool):
        # Simulate file exists
        files_tool.sandbox.fs.get_file_info.return_value = MagicMock()

        result = await files_tool.full_file_rewrite("existing_file.txt", "new content", "600")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "File 'existing_file.txt' completely rewritten successfully." in result.output

        files_tool.sandbox.fs.upload_file.assert_awaited_once_with("/workspace/existing_file.txt", b"new content")
        files_tool.sandbox.fs.set_file_permissions.assert_awaited_once_with("/workspace/existing_file.txt", "600")
        files_tool._ensure_sandbox.assert_awaited_once()

    async def test_full_file_rewrite_file_not_exist(self, files_tool):
        # Simulate file doesn't exist
        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")

        result = await files_tool.full_file_rewrite("non_existent_file.txt", "content") # Default perm "644"

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "File 'non_existent_file.txt' does not exist." in result.output
        files_tool.sandbox.fs.upload_file.assert_not_called()
        files_tool.sandbox.fs.set_file_permissions.assert_not_called()

    async def test_full_file_rewrite_index_html(self, files_tool):
        files_tool.sandbox.fs.get_file_info.return_value = MagicMock()

        result = await files_tool.full_file_rewrite("index.html", "new html content") # Default perm "644"

        assert result.success is True
        assert "File 'index.html' completely rewritten successfully." in result.output
        assert "[Auto-detected index.html - HTTP server available at: http://fake.preview/index.html]" in result.output
        files_tool.sandbox.fs.upload_file.assert_awaited_once_with("/workspace/index.html", b"new html content")
        files_tool.sandbox.fs.set_file_permissions.assert_awaited_once_with("/workspace/index.html", "644")
        files_tool.sandbox.get_preview_link.assert_called_once_with(8080)

    # Example of testing a failure in an fs operation
    async def test_create_file_fs_create_folder_fails(self, files_tool):
        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")
        # Simulate failure in create_folder by making it raise an exception
        files_tool.sandbox.fs.create_folder.side_effect = Exception("mkdir failed by test")

        result = await files_tool.create_file("test_dir/new_file.txt", "content")

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "Error creating file: mkdir failed by test" in result.output
        files_tool.sandbox.fs.create_folder.assert_awaited_once()
        files_tool.sandbox.fs.upload_file.assert_not_called()
        files_tool.sandbox.fs.set_file_permissions.assert_not_called()

    async def test_create_file_fs_upload_fails(self, files_tool):
        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")
        files_tool.sandbox.fs.upload_file.side_effect = Exception("Upload permission denied by test")

        result = await files_tool.create_file("another_dir/another_file.txt", "content")

        assert result.success is False
        assert "Error creating file: Upload permission denied by test" in result.output
        files_tool.sandbox.fs.create_folder.assert_awaited_once() # Assuming this succeeded
        files_tool.sandbox.fs.upload_file.assert_awaited_once()
        files_tool.sandbox.fs.set_file_permissions.assert_not_called()

    async def test_create_file_fs_set_permissions_fails(self, files_tool):
        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")
        files_tool.sandbox.fs.set_file_permissions.side_effect = Exception("chmod failed by test")

        result = await files_tool.create_file("perm_fail_dir/perm_fail_file.txt", "content")

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "Error creating file: chmod failed by test" in result.output
        files_tool.sandbox.fs.create_folder.assert_awaited_once()
        files_tool.sandbox.fs.upload_file.assert_awaited_once()
        files_tool.sandbox.fs.set_file_permissions.assert_awaited_once()

    async def test_full_file_rewrite_fs_upload_fails(self, files_tool):
        files_tool.sandbox.fs.get_file_info.return_value = MagicMock() # File exists
        files_tool.sandbox.fs.upload_file.side_effect = Exception("Upload failed during rewrite by test")

        result = await files_tool.full_file_rewrite("existing_file_for_rewrite_fail.txt", "new content")

        assert result.success is False
        assert "Error rewriting file: Upload failed during rewrite by test" in result.output
        files_tool.sandbox.fs.upload_file.assert_awaited_once()
        files_tool.sandbox.fs.set_file_permissions.assert_not_called()

    async def test_full_file_rewrite_fs_set_permissions_fails(self, files_tool):
        files_tool.sandbox.fs.get_file_info.return_value = MagicMock() # File exists
        files_tool.sandbox.fs.set_file_permissions.side_effect = Exception("chmod failed during rewrite by test")

        result = await files_tool.full_file_rewrite("existing_file_for_rewrite_perm_fail.txt", "new content")

        assert result.success is False
        assert "Error rewriting file: chmod failed during rewrite by test" in result.output
        files_tool.sandbox.fs.upload_file.assert_awaited_once() # Upload should have been called
        files_tool.sandbox.fs.set_file_permissions.assert_awaited_once()

    async def test_clean_path_usage(self, files_tool):
        # This test is more about ensuring clean_path is used, which is implicitly tested
        # by the /workspace/ prefix in other assertions.
        # Here, we can explicitly check the behavior of clean_path if it were more complex.
        # For now, this just confirms it prepends /workspace correctly.
        raw_path = "some/file.txt"
        cleaned = files_tool.clean_path(raw_path) # clean_path is synchronous
        assert cleaned == "some/file.txt" # clean_path itself doesn't add /workspace if base is /workspace

        # The full_path construction in methods is f"{self.workspace_path}/{file_path}"
        # where file_path is already cleaned.
        # So, if file_path from clean_path is "some/file.txt", full_path becomes "/workspace/some/file.txt".

        files_tool.sandbox.fs.get_file_info.side_effect = Exception("File not found")
        await files_tool.create_file(raw_path, "content")
        files_tool.sandbox.fs.upload_file.assert_awaited_with("/workspace/some/file.txt", b"content")
