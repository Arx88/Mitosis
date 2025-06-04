import docker
import logging
import os
import tarfile
import io
from typing import Optional, Dict, List, Tuple, Any

logger = logging.getLogger(__name__) # Or from utils.logger if available and preferred

client: Optional[docker.DockerClient] = None

def _get_or_initialize_client() -> Optional[docker.DockerClient]:
    """
    Initializes the Docker client if it's not already initialized.
    Returns the client instance or None if initialization fails.
    """
    global client
    if client is None:
        logger.info("Docker client is None, attempting initialization.")
        try:
            # Explicitly try the standard Unix socket first, as it's mounted.
            temp_client = docker.DockerClient(base_url='unix:///var/run/docker.sock', timeout=10)
            temp_client.ping() # Verify connection
            logger.info("Docker client initialized successfully via unix:///var/run/docker.sock and connected to Docker daemon.")
            client = temp_client
        except docker.errors.DockerException as e_unix_socket:
            logger.warning(
                f"Failed to initialize Docker client via unix:///var/run/docker.sock. Error: {e_unix_socket}. "
                f"Attempting docker.from_env() as a fallback."
            )
            try:
                temp_client = docker.from_env(timeout=10) # Added timeout here as well for consistency
                temp_client.ping() # Verify connection
                logger.info("Docker client initialized successfully via docker.from_env() and connected to Docker daemon.")
                client = temp_client
            except docker.errors.DockerException as e_from_env:
                logger.error(
                    f"Failed to initialize Docker client via docker.from_env() as well. "
                    f"Ensure Docker is running and accessible. Error: {e_from_env}"
                )
                # client remains None if all attempts fail
    return client

def start_sandbox_container(image_name: str, env_vars: Dict[str, str], project_id: Optional[str] = None,
                            vnc_port_host: Optional[int] = None, web_port_host: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Creates and starts a new Docker container locally to act as a sandbox.
    Returns a dictionary with container_id, host_vnc_port, host_web_port.
    Allows specifying host ports for easier local dev, otherwise Docker assigns random ones.
    """
    current_client = _get_or_initialize_client()
    if not current_client:
        logger.error("Docker client not available. Cannot start sandbox container.")
        return None

    logger.info(f"Attempting to create local Docker sandbox for project_id: {project_id} using image: {image_name}")

    try:
        # Pull the image if not present (optional, run can also do this)
        # For simplicity, let's assume image is pulled or run will handle it.
        # current_client.images.pull(image_name)
        # logger.info(f"Ensured image {image_name} is available.")

        ports_map = {}
        if vnc_port_host:
            ports_map['6080/tcp'] = vnc_port_host
        else:
            ports_map['6080/tcp'] = None # Assign a random available host port

        if web_port_host:
            ports_map['8080/tcp'] = web_port_host
        else:
            ports_map['8080/tcp'] = None # Assign a random available host port

        container_labels = {'managed_by': 'agentpress_local_sandbox'}
        if project_id:
            container_labels['project_id'] = project_id

        container_name = f"agentpress_sandbox_{project_id or os.urandom(4).hex()}"

        container = current_client.containers.run(
            image=image_name,
            detach=True,
            environment=env_vars,
            ports=ports_map,
            labels=container_labels,
            name=container_name,
            # Consider adding remove=True for auto-cleanup if desired,
            # but for sandboxes, manual cleanup via delete_sandbox is typical.
            # remove=True
        )
        logger.info(f"Local Docker sandbox container {container.id} started with name {container_name}.")

        container.reload() # To get updated port information

        actual_host_vnc_port = None
        if container.ports.get('6080/tcp'):
            actual_host_vnc_port = container.ports['6080/tcp'][0]['HostPort']

        actual_host_web_port = None
        if container.ports.get('8080/tcp'):
            actual_host_web_port = container.ports['8080/tcp'][0]['HostPort']

        logger.info(f"Container {container.id} ports: VNC -> {actual_host_vnc_port}, Web -> {actual_host_web_port}")

        return {
            'container_id': container.id,
            'container_name': container.name,
            'host_vnc_port': actual_host_vnc_port,
            'host_web_port': actual_host_web_port,
            'status': container.status
        }

    except docker.errors.ImageNotFound:
        logger.error(f"Docker image {image_name} not found.")
        return None
    except docker.errors.APIError as e:
        logger.error(f"Docker API error while starting container: {e}")
        if "port is already allocated" in str(e) and (vnc_port_host or web_port_host):
            logger.error(f"One of the specified host ports ({vnc_port_host}, {web_port_host}) might be in use.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error starting local Docker sandbox: {e}", exc_info=True)
        return None

def stop_and_remove_sandbox_container(container_id: str, raise_not_found: bool = False) -> bool:
    """Stops and removes a local Docker sandbox container by ID or name."""
    current_client = _get_or_initialize_client()
    if not current_client:
        logger.error("Docker client not available. Cannot stop/remove sandbox container.")
        return False
    try:
        container = current_client.containers.get(container_id)
        logger.info(f"Stopping container {container.id}...")
        container.stop(timeout=5)
        logger.info(f"Removing container {container.id}...")
        container.remove()
        logger.info(f"Container {container.id} stopped and removed.")
        return True
    except docker.errors.NotFound:
        logger.warning(f"Container {container_id} not found for stop/remove.")
        if raise_not_found:
            raise
        return False
    except docker.errors.APIError as e:
        logger.error(f"Docker API error stopping/removing container {container_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error stopping/removing local Docker sandbox {container_id}: {e}", exc_info=True)
        return False

def get_sandbox_container_status(container_id: str) -> Optional[str]:
    """Gets the status of a local Docker sandbox container."""
    current_client = _get_or_initialize_client()
    if not current_client:
        logger.error("Docker client not available. Cannot get container status.")
        return None
    try:
        container = current_client.containers.get(container_id)
        return container.status
    except docker.errors.NotFound:
        logger.warning(f"Container {container_id} not found when checking status.")
        return "not_found"
    except Exception as e:
        logger.error(f"Error getting status for container {container_id}: {e}", exc_info=True)
        return "error"

def execute_command_in_container(container_id: str, command: str, workdir: str = "/workspace", timeout_seconds: int = 60) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Executes a command in the specified local Docker sandbox container.
    Returns (stdout_str, stderr_str, exit_code).
    Timeout is not directly supported by exec_run in the same way as subprocess,
    but Docker's exec_run itself has a default timeout or can be wrapped if long running task.
    For now, we rely on Docker's default exec timeout behavior.
    """
    current_client = _get_or_initialize_client()
    if not current_client:
        logger.error("Docker client not available. Cannot execute command.")
        return None, "Docker client not available", -1

    logger.info(f"Executing command in container {container_id} at {workdir}: {command}")
    try:
        container = current_client.containers.get(container_id)
        # The timeout for exec_run is complex; it's for the API call, not the command execution itself.
        # For true command timeout, a more complex async handling or streaming output and checking time would be needed.
        exit_code, (stdout_bytes, stderr_bytes) = container.exec_run(cmd=command, workdir=workdir, demux=True)

        stdout_str = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ""
        stderr_str = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ""

        logger.debug(f"Command executed. Exit code: {exit_code}. Stdout: {stdout_str[:200]}...Stderr: {stderr_str[:200]}...")
        return stdout_str, stderr_str, exit_code
    except docker.errors.NotFound:
        logger.error(f"Container {container_id} not found for command execution.")
        return None, "Container not found", -1
    except docker.errors.APIError as e:
        logger.error(f"Docker API error executing command in {container_id}: {e}")
        return None, str(e), -1
    except Exception as e:
        logger.error(f"Unexpected error executing command in {container_id}: {e}", exc_info=True)
        return None, str(e), -1

def upload_files_to_container(container_id: str, host_path: str, container_path: str) -> bool:
    """
    Uploads a file or directory from the host to the specified path in the local Docker sandbox.
    host_path: Path on the host.
    container_path: Absolute path in the container where the contents of host_path should be placed.
                   If host_path is a file, this is the full file path in container.
                   If host_path is a dir, this is the parent dir in container.
    """
    current_client = _get_or_initialize_client()
    if not current_client:
        logger.error("Docker client not available. Cannot upload files.")
        return False

    logger.info(f"Uploading from host:'{host_path}' to container:'{container_id}:{container_path}'")

    try:
        container = current_client.containers.get(container_id)

        # Create a tarball in memory
        pw_tarstream = io.BytesIO()
        with tarfile.open(fileobj=pw_tarstream, mode='w') as tar:
            # arcname ensures the files/dirs are added to the tar root, not with full host path
            tar.add(host_path, arcname=os.path.basename(host_path))

        pw_tarstream.seek(0) # Go to the beginning of the stream

        # If container_path is a full path to a file, we need to put it into its directory
        # and the tarball should only contain the file itself at the root.
        # If it's a directory, put_archive expects the tar to be extracted *into* that path.
        # For now, let's assume container_path is the directory where os.path.basename(host_path) will land.
        # If host_path is /tmp/foo.txt and container_path is /workspace, foo.txt lands in /workspace/foo.txt
        # If host_path is /tmp/mydir and container_path is /workspace, mydir lands in /workspace/mydir

        # Ensure the target directory exists in the container
        target_parent_dir = os.path.dirname(container_path) if '.' in os.path.basename(container_path) else container_path
        if target_parent_dir != '/': # Avoid trying to create root
             # Create the directory path, including any intermediate directories
            exit_code_mkdir, (out_mkdir, err_mkdir) = container.exec_run(cmd=f"mkdir -p {target_parent_dir}", workdir="/")
            if exit_code_mkdir != 0:
                logger.error(f"Failed to create directory {target_parent_dir} in container {container_id}. Error: {err_mkdir.decode('utf-8', errors='replace')}")
                # Not returning False here, put_archive might still work if dir exists or is root.

        if container.put_archive(path=target_parent_dir, data=pw_tarstream):
            logger.info(f"Successfully uploaded {host_path} to {container_id}:{container_path}")
            return True
        else:
            logger.error(f"Failed to upload {host_path} to {container_id}:{container_path} (put_archive returned False)")
            return False

    except docker.errors.NotFound:
        logger.error(f"Container {container_id} not found for file upload.")
        return False
    except FileNotFoundError:
        logger.error(f"Host path {host_path} not found for upload.")
        return False
    except Exception as e:
        logger.error(f"Error uploading to container {container_id}: {e}", exc_info=True)
        return False

def list_files_in_container(container_id: str, path: str) -> List[Dict[str, Any]]:
    """
    Lists files and directories at the specified path in the local Docker sandbox.
    Returns a list of dicts with 'name', 'type' ('file'/'directory'), and 'size'.
    Basic implementation, might not handle all edge cases of ls output.
    """
    current_client = _get_or_initialize_client()
    if not current_client:
        logger.error("Docker client not available. Cannot list files.")
        return []

    logger.info(f"Listing files in {container_id}:{path}")
    # Using ls -l --time-style=long-iso to get details. -A to include dotfiles except . and ..
    # The output parsing will be basic.
    # Example line: drwxr-xr-x 2 root root 4096 2023-04-15 10:00 mydir
    # Example line: -rw-r--r-- 1 root root 1024 2023-04-15 10:01 file.txt
    # command = f"ls -lA --full-time --time-style=long-iso {path}" # --full-time is GNU specific
    command = f"ls -lA --time-style=long-iso {path}"

    try:
        container = current_client.containers.get(container_id)
        exit_code, (stdout_bytes, stderr_bytes) = container.exec_run(cmd=command, workdir="/") # workdir usually doesn't matter for absolute paths

        if exit_code != 0:
            stderr_str = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ""
            logger.error(f"Error listing files in {container_id}:{path}. Exit code: {exit_code}. Stderr: {stderr_str}")
            return []

        stdout_str = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ""
        files = []
        lines = stdout_str.strip().split('\n')

        if lines and "total" in lines[0]: # First line of ls -l is often "total X"
            lines = lines[1:]

        for line in lines:
            if not line.strip():
                continue
            parts = line.split(None, 8) # Split by whitespace, max 8 splits for ls -l format
            if len(parts) < 9:
                logger.warning(f"Could not parse ls line: '{line}' in {container_id}:{path}")
                continue

            permissions = parts[0]
            size_bytes = int(parts[4])
            name = parts[8]

            file_type = "unknown"
            if permissions.startswith('d'):
                file_type = "directory"
            elif permissions.startswith('-'):
                file_type = "file"
            # Other types like 'l' for symlink, 'c' for char dev, 'b' for block dev etc.

            files.append({
                "name": name,
                "type": file_type,
                "size": size_bytes,
                # "permissions": permissions,
                # "last_modified": f"{parts[5]} {parts[6]} {parts[7]}" # Date time parts
            })
        return files

    except docker.errors.NotFound:
        logger.error(f"Container {container_id} not found for file listing.")
        return []
    except Exception as e:
        logger.error(f"Error listing files in {container_id}:{path}: {e}", exc_info=True)
        return []

def get_container_logs(container_id: str, tail: str = "all") -> Optional[str]:
    """Fetches logs from a container."""
    current_client = _get_or_initialize_client()
    if not current_client:
        logger.error("Docker client not available. Cannot fetch logs.")
        return None
    try:
        container = current_client.containers.get(container_id)
        log_bytes = container.logs(stdout=True, stderr=True, timestamps=True, tail=tail if isinstance(tail, int) else (500 if tail == "all" else tail) ) # tail="all" is not a valid SDK value for tail, use a large number
        return log_bytes.decode('utf-8', errors='replace')
    except docker.errors.NotFound:
        logger.warning(f"Container {container_id} not found when fetching logs.")
        return "Container not found."
    except Exception as e:
        logger.error(f"Error fetching logs for container {container_id}: {e}", exc_info=True)
        return f"Error fetching logs: {str(e)}"
