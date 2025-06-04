import pytest
from unittest.mock import patch, AsyncMock
# Assuming 'backend' is in PYTHONPATH or is the root for test discovery
from sandbox.sandbox import LocalDockerFileSystemWrapper

# Note: local_docker_handler is imported within sandbox.sandbox,
# so we patch it there.

@pytest.mark.asyncio
class TestLocalDockerFileSystemWrapper:

    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_success(self, mock_execute_command):
        # Mock successful mkdir and chmod
        # execute_command_in_container returns (stdout, stderr, exit_code)
        mock_execute_command.side_effect = [
            ('', '', 0),  # mkdir success
            ('', '', 0)   # chmod success
        ]

        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        # create_folder is async
        result = await wrapper.create_folder("/test/folder", "777")

        assert result is True
        assert mock_execute_command.call_count == 2

        # Check mkdir call
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p /test/folder"
            # workdir is a kwarg with default in the actual function, not asserted here unless critical
        )
        # Check chmod call
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod 777 /test/folder"
        )

    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_mkdir_fails(self, mock_execute_command):
        # Mock mkdir failure
        mock_execute_command.return_value = ('', 'Error making dir', 1) # exit_code = 1

        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("/test/folder_fail_mkdir")

        assert result is False
        # Only mkdir should be called
        mock_execute_command.assert_called_once_with(
            container_id="test_container",
            command="mkdir -p /test/folder_fail_mkdir"
        )

    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_chmod_fails(self, mock_execute_command):
        # Mock mkdir success, chmod failure
        mock_execute_command.side_effect = [
            ('', '', 0),  # mkdir success
            ('', 'Error setting perms', 1)   # chmod failure, exit_code = 1
        ]

        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("/test/folder_fail_chmod", "700")

        assert result is False
        assert mock_execute_command.call_count == 2
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p /test/folder_fail_chmod"
        )
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod 700 /test/folder_fail_chmod"
        )

    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_default_permissions(self, mock_execute_command):
        mock_execute_command.side_effect = [
            ('', '', 0), # mkdir
            ('', '', 0)  # chmod
        ]
        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("/test/default_perms_folder")

        assert result is True
        assert mock_execute_command.call_count == 2
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p /test/default_perms_folder"
        )
        # Default permission is "755"
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod 755 /test/default_perms_folder"
        )

    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_nested_folders_success(self, mock_execute_command):
        # mkdir -p handles nested creation
        mock_execute_command.side_effect = [
            ('', '', 0),
            ('', '', 0)
        ]
        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("/test/very/deeply/nested/path", "775")

        assert result is True
        assert mock_execute_command.call_count == 2
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p /test/very/deeply/nested/path"
        )
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod 775 /test/very/deeply/nested/path"
        )

    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_already_exists(self, mock_execute_command):
        # mkdir -p doesn't fail if the folder exists. Chmod should still be called.
        mock_execute_command.side_effect = [
            ('', '', 0), # mkdir -p (no error if exists)
            ('', '', 0)  # chmod
        ]
        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("/test/existing_folder", "750")

        assert result is True
        assert mock_execute_command.call_count == 2
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p /test/existing_folder"
        )
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod 750 /test/existing_folder"
        )

    # Test with empty folder_path - this should ideally be handled,
    # though mkdir -p "" might create in current dir or error.
    # Let's assume the command execution will handle it (e.g. return non-zero exit code)
    # or the calling code to create_folder ensures path is valid.
    # For now, we'll assume valid paths are passed.
    # If specific error handling for empty path is in create_folder, it should be tested.
    # The current create_folder does not have specific validation for folder_path.
    # It relies on mkdir's behavior.
    # Example: mkdir -p "" might do nothing or error depending on shell/OS.
    # In most Linux shells, `mkdir -p ""` is a no-op and returns success.
    # `chmod 755 ""` would also likely be a no-op or error subtly.
    # Let's test this behavior.
    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_empty_path(self, mock_execute_command):
        mock_execute_command.side_effect = [
            ('', '', 0),  # Assume mkdir -p "" is success (no-op)
            ('', '', 0)   # Assume chmod 755 "" is success (no-op) or not harmful
        ]

        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("", "700") # Intentionally empty path

        assert result is True # Based on typical "mkdir -p """ behavior
        assert mock_execute_command.call_count == 2

        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p " # Empty path
        )
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod 700 " # Empty path
        )

    # Test with folder_path being just "/"
    # mkdir -p / is a no-op and succeeds. chmod on / might fail depending on user.
    # Let's assume for this test that chmod on / also succeeds for simplicity of mocking.
    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_root_path(self, mock_execute_command):
        mock_execute_command.side_effect = [
            ('', '', 0),  # mkdir -p / (success, no-op)
            ('', '', 0)   # chmod 755 / (assume success for mock)
        ]

        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("/", "755")

        assert result is True
        assert mock_execute_command.call_count == 2

        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p /"
        )
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod 755 /"
        )

    # Test for path with spaces - should be handled by shell if commands are well-formed
    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_with_spaces_in_path(self, mock_execute_command):
        mock_execute_command.side_effect = [
            ('', '', 0),
            ('', '', 0)
        ]
        folder_path_with_spaces = "/test/folder with spaces"
        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder(folder_path_with_spaces, "755")

        assert result is True
        assert mock_execute_command.call_count == 2
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command=f"mkdir -p {folder_path_with_spaces}" # f-string will correctly include spaces
        )
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command=f"chmod 755 {folder_path_with_spaces}"
        )

    # Test for permissions string that might be invalid for chmod (e.g. "abc")
    # The create_folder method doesn't validate permissions string.
    # It's passed directly to chmod. Chmod will fail.
    @patch('sandbox.sandbox.local_docker_handler.execute_command_in_container')
    async def test_create_folder_invalid_permissions_string(self, mock_execute_command):
        mock_execute_command.side_effect = [
            ('', '', 0),                            # mkdir success
            ('', 'chmod: invalid mode: abc', 1)     # chmod failure
        ]
        wrapper = LocalDockerFileSystemWrapper(container_id="test_container")
        result = await wrapper.create_folder("/test/invalid_perms", "abc")

        assert result is False # Chmod fails
        assert mock_execute_command.call_count == 2
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="mkdir -p /test/invalid_perms"
        )
        mock_execute_command.assert_any_call(
            container_id="test_container",
            command="chmod abc /test/invalid_perms"
        )
