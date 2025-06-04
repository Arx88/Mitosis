import asyncio
import os
from unittest.mock import MagicMock, AsyncMock, patch
import sys

sys.path.insert(0, '/app/backend')

mock_logger = MagicMock()
sys.modules['utils.logger'] = mock_logger

import sandbox.tool_base
import sandbox.local_docker_handler

from sandbox.sandbox import LocalDockerFileSystemWrapper
from agent.tools.sb_files_tool import SandboxFilesTool

# --- Mock implementations ---
async def mock_execute_command_in_container_impl(container_id, command, workdir="/workspace", timeout_seconds=60):
    mock_logger.info(f"Mock exec: ID={container_id}, Cmd='{command}'")
    if "mkdir -p" in command or "chmod" in command:
        return "", "", 0
    mock_logger.error(f"Unhandled cmd in mock_exec: {command}")
    return "stdout_err", "stderr_err", 1

def mock_upload_files_to_container_impl(container_id, host_path, container_path):
    mock_logger.info(f"Mock upload: ID={container_id}, Host='{host_path}', Cont='{container_path}'")
    if os.path.exists(host_path):
        try:
            os.remove(host_path)
        except Exception as e:
            mock_logger.error(f"Err removing {host_path} in mock: {e}")
    return True

get_or_start_sandbox_call_count = 0
last_get_or_start_sandbox_args = None

async def actual_mock_get_or_start_sandbox(project_id, db_client_arg, mock_sandbox_obj_to_return):
    global get_or_start_sandbox_call_count, last_get_or_start_sandbox_args
    get_or_start_sandbox_call_count += 1
    last_get_or_start_sandbox_args = (project_id, db_client_arg)
    mock_logger.info(f"actual_mock_get_or_start_sandbox called for project_id: {project_id} with client: {type(db_client_arg)}")
    return mock_sandbox_obj_to_return

async def main():
    print("Integration Test: Start")

    fs_wrapper = LocalDockerFileSystemWrapper(container_id="test_container_id")
    mock_sandbox_object = MagicMock(spec=LocalDockerFileSystemWrapper)
    mock_sandbox_object.fs = fs_wrapper
    mock_sandbox_object.id = "test_sandbox_id_from_mock_obj"

    global mock_exec_patched

    if not hasattr(LocalDockerFileSystemWrapper, 'set_file_permissions'):
        print("Warning: Mocking set_file_permissions on LocalDockerFileSystemWrapper instance.")
        async def mock_sfp_instance(self_fs, file_path: str, permissions: str) -> bool:
            mock_logger.info(f"[MockFS-Inst] set_perms: {self_fs.container_id}:{file_path} to {permissions}")
            _, _, exit_code = await mock_exec_patched(self_fs.container_id, f"chmod {permissions} {file_path}")
            return exit_code == 0
        fs_wrapper.set_file_permissions = AsyncMock(wraps=lambda path, perms: mock_sfp_instance(fs_wrapper, path, perms))

    async def get_or_start_sandbox_for_patch(project_id, db_client_arg):
        return await actual_mock_get_or_start_sandbox(project_id, db_client_arg, mock_sandbox_object)

    with patch.object(sandbox.local_docker_handler, 'execute_command_in_container', new_callable=AsyncMock) as mock_exec, \
         patch.object(sandbox.local_docker_handler, 'upload_files_to_container', new_callable=MagicMock) as mock_upload, \
         patch.object(sandbox.tool_base, 'get_or_start_sandbox', new=get_or_start_sandbox_for_patch) as manual_mock_get_sandbox:

        mock_exec_patched = mock_exec
        mock_exec.side_effect = mock_execute_command_in_container_impl
        mock_upload.side_effect = mock_upload_files_to_container_impl

        mock_actual_supabase_client = AsyncMock()

        # Create an AsyncMock for the client_accessor *function*
        db_client_accessor_mock = AsyncMock(return_value=mock_actual_supabase_client)

        mock_thread_manager = MagicMock()
        mock_thread_manager.db = MagicMock()
        # self.thread_manager.db.client should be a coroutine object if it's awaited directly
        # So, it should be the result of calling an async function mock
        mock_thread_manager.db.client = db_client_accessor_mock() # client is a coroutine object

        files_tool = SandboxFilesTool(project_id="test_project_id", thread_manager=mock_thread_manager)

        file_path_to_create = "test_dir/test_subdir/test_file.txt"
        file_content = "content for test file"
        permissions = "644"

        attribute_error_raised = False
        try:
            print(f"DEBUG: files_tool._sandbox before explicit _ensure_sandbox: {getattr(files_tool, '_sandbox', 'NotSet')}")
            await files_tool._ensure_sandbox()
            print(f"DEBUG: files_tool._sandbox after explicit _ensure_sandbox: {getattr(files_tool, '_sandbox', 'NotSet')}")
            print(f"DEBUG: get_or_start_sandbox_call_count after explicit _ensure_sandbox: {get_or_start_sandbox_call_count}")

            print(f"Test: Calling create_file for {file_path_to_create}")
            await files_tool.create_file(file_path_to_create, file_content, permissions)
            print(f"Test: create_file call completed.")

            assert get_or_start_sandbox_call_count >= 1, f"Expected actual_mock_get_or_start_sandbox to be called at least once. Called {get_or_start_sandbox_call_count} times."
            if get_or_start_sandbox_call_count >= 1:
                 assert last_get_or_start_sandbox_args == ("test_project_id", mock_actual_supabase_client), f"Call args mismatch: expected client {type(mock_actual_supabase_client)}, got {type(last_get_or_start_sandbox_args[1]) if last_get_or_start_sandbox_args else 'None'}"
            print("Test: Manual mock for get_or_start_sandbox was called correctly.")

            mock_exec.assert_any_call(container_id='test_container_id', command='mkdir -p /workspace/test_dir/test_subdir')
            mock_exec.assert_any_call(container_id='test_container_id', command='chmod 755 /workspace/test_dir/test_subdir')

            upload_called_correctly = any(
                ca[0][0] == 'test_container_id' and ca[0][2] == f"/workspace/{file_path_to_create}"
                for ca in mock_upload.call_args_list
            )
            assert upload_called_correctly, f"upload_files_to_container not called as expected. Calls: {mock_upload.call_args_list}"

            expected_chmod_file_cmd = f'chmod {permissions} /workspace/{file_path_to_create}'
            if isinstance(getattr(fs_wrapper, 'set_file_permissions', None), AsyncMock) and \
               fs_wrapper.set_file_permissions.called:
                fs_wrapper.set_file_permissions.assert_called_with(f"/workspace/{file_path_to_create}", permissions)
                print("Test: Instance mock of set_file_permissions was asserted.")
                found_chmod_call_via_mock = any(
                    call_args.kwargs.get('command') == expected_chmod_file_cmd and call_args.kwargs.get('container_id') == 'test_container_id'
                    for call_args in mock_exec.call_args_list
                )
                assert found_chmod_call_via_mock, f"Expected chmod call for file not found via mock set_file_permissions. Exec calls: {mock_exec.call_args_list}"
            elif hasattr(LocalDockerFileSystemWrapper, 'set_file_permissions'):
                mock_exec.assert_any_call(container_id='test_container_id', command=expected_chmod_file_cmd)
                print("Test: Actual set_file_permissions (using execute_command_in_container) was asserted.")
            else:
                assert False, "set_file_permissions was not available or not called."

            print("Test: Assertions passed.")

        except AttributeError as e:
            if 'create_folder' in str(e):
                print(f"FAILURE: AttributeError for 'create_folder' was raised: {e}")
                attribute_error_raised = True
            else:
                print(f"FAILURE: Unexpected AttributeError: {e}")
                import traceback
                traceback.print_exc()
                raise
        except Exception as e:
            print(f"FAILURE: Unexpected error: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            raise

        if attribute_error_raised:
            print("Test Result: FAIL (AttributeError for create_folder)")
            sys.exit(1)
        else:
            print("Test Result: SUCCESS (No 'create_folder' AttributeError and other assertions passed)")

if __name__ == "__main__":
    asyncio.run(main())
