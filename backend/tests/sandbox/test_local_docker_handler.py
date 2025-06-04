import unittest
from unittest import mock
import os

if 'ENV_MODE' not in os.environ:
    os.environ['ENV_MODE'] = 'test'

patch_target_docker = 'backend.sandbox.local_docker_handler.docker'
mock_logger = mock.MagicMock()

@mock.patch(patch_target_docker)
@mock.patch('backend.sandbox.local_docker_handler.logger', mock_logger)
class TestLocalDockerHandlerOnDemandInit(unittest.TestCase):

    def setUp(self):
        from backend.sandbox import local_docker_handler
        local_docker_handler.client = None
        self.local_docker_handler = local_docker_handler
        # self.mock_docker_lib_instance is no longer needed here, use the decorator-injected mock for docker module

        # The mock_logger is already defined at the module level and passed to the decorator.
        # We will use the argument passed by the decorator for logger for clarity within tests if needed,
        # or directly use module-level 'mock_logger' for assertions.
        # For DockerClient and from_env, they need to be attributes of the *mocked docker module*
        # which is passed as an argument to the test methods.
        mock_logger.reset_mock() # Reset the module-level logger mock

    def tearDown(self):
        # mock.patch.stopall() # Not strictly necessary if only using class decorators, but good for safety if other patches are added.
        # However, if we removed the .start() in setUp, this might cause issues if not balanced.
        # Class decorators are managed by the test runner.
        pass # Let class decorators handle their own start/stop

    # Arguments are passed from inner decorator outwards:
    # 1. logger_mock (from @mock.patch('...logger', mock_logger)) -> NO LONGER PASSED
    # 2. docker_mock (from @mock.patch(patch_target_docker)) -> This is the only one passed
    def test_initialization_failure_then_success(self, passed_docker_mock):
        # Configure mocks for this specific test
        # passed_docker_mock.DockerClient and passed_docker_mock.from_env are MagicMocks by default.
        # passed_docker_mock.errors.DockerException needs to be an actual exception class for 'except' clauses
        mock_docker_exception_class = Exception # Use a real exception class
        passed_docker_mock.errors.DockerException = mock_docker_exception_class

        mock_docker_exception_instance = mock_docker_exception_class("Simulated Docker Error")

        passed_docker_mock.DockerClient.side_effect = mock_docker_exception_instance
        passed_docker_mock.from_env.side_effect = mock_docker_exception_instance

        status = self.local_docker_handler.get_sandbox_container_status("dummy_id")
        self.assertIsNone(status, "Status should be None on client init failure")
        self.assertIsNone(self.local_docker_handler.client, "Global client should remain None after failed init")
        mock_logger.error.assert_any_call(f"Failed to initialize Docker client via docker.from_env() as well. Ensure Docker is running and accessible. Error: {mock_docker_exception_instance}")

        mock_logger.reset_mock()
        # Reset DockerClient and from_env mocks for the next part of the test
        passed_docker_mock.DockerClient = mock.MagicMock(side_effect=mock_docker_exception_instance)
        passed_docker_mock.from_env = mock.MagicMock()


        mock_successful_client = mock.MagicMock() # Removed spec to allow arbitrary attributes like 'ping'
        mock_successful_client.ping.return_value = True

        # DockerClient still fails, from_env will now succeed
        passed_docker_mock.from_env.side_effect = None
        passed_docker_mock.from_env.return_value = mock_successful_client

        mock_container = mock.MagicMock()
        mock_container.status = "running"
        mock_successful_client.containers.get.return_value = mock_container

        status = self.local_docker_handler.get_sandbox_container_status("dummy_id_2")
        self.assertEqual(status, "running", "Status should be 'running' after successful client init")
        self.assertIsNotNone(self.local_docker_handler.client, "Global client should be initialized")
        self.assertEqual(self.local_docker_handler.client, mock_successful_client, "Global client should be the successfully created one")
        mock_successful_client.containers.get.assert_called_once_with("dummy_id_2")
        mock_logger.info.assert_any_call("Docker client initialized successfully via docker.from_env() and connected to Docker daemon.")

    def test_persistent_initialization_failure(self, passed_docker_mock):
        mock_docker_exception_class = Exception
        passed_docker_mock.errors.DockerException = mock_docker_exception_class
        mock_docker_exception_instance = mock_docker_exception_class("Simulated Persistent Docker Error")

        passed_docker_mock.DockerClient.side_effect = mock_docker_exception_instance
        passed_docker_mock.from_env.side_effect = mock_docker_exception_instance

        result = self.local_docker_handler.start_sandbox_container("image", {})
        self.assertIsNone(result, "start_sandbox_container should return None on persistent client failure")
        self.assertIsNone(self.local_docker_handler.client, "Global client should remain None")
        mock_logger.error.assert_any_call("Docker client not available. Cannot start sandbox container.")
        mock_logger.error.assert_any_call(f"Failed to initialize Docker client via docker.from_env() as well. Ensure Docker is running and accessible. Error: {mock_docker_exception_instance}")


    def test_initialization_success_on_first_attempt_socket(self, passed_docker_mock):
        mock_docker_exception_class = Exception
        passed_docker_mock.errors.DockerException = mock_docker_exception_class # For any potential except clauses

        mock_successful_client = mock.MagicMock() # Removed spec
        mock_successful_client.ping.return_value = True

        passed_docker_mock.DockerClient.return_value = mock_successful_client
        passed_docker_mock.from_env.side_effect = Exception("from_env should not have been called")


        mock_container = mock.MagicMock()
        mock_container.status = "running"
        mock_successful_client.containers.get.return_value = mock_container

        status = self.local_docker_handler.get_sandbox_container_status("dummy_id_socket")
        self.assertEqual(status, "running", "Status should be 'running' on successful socket init")
        self.assertIsNotNone(self.local_docker_handler.client, "Global client should be initialized")
        self.assertEqual(self.local_docker_handler.client, mock_successful_client, "Global client should be the one from DockerClient")

        passed_docker_mock.DockerClient.assert_called_once()
        passed_docker_mock.from_env.assert_not_called()
        mock_successful_client.containers.get.assert_called_once_with("dummy_id_socket")
        mock_logger.info.assert_any_call("Docker client initialized successfully via unix:///var/run/docker.sock and connected to Docker daemon.")

if __name__ == '__main__':
    # Need to make sure local_docker_handler.docker.errors.DockerException is properly mocked if tests run directly
    # This is typically handled by the test runner and class decorators when run via `python -m unittest`
    # For direct script execution, ensure mocks are active.
    # However, the current structure with class decorators should be fine with `python -m unittest`.
    unittest.main()
