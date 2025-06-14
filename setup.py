#!/usr/bin/env python3
import os
import sys
import time
import platform
import subprocess
from getpass import getpass
import re
import json


IS_WINDOWS = platform.system() == 'Windows'

# ANSI colors for pretty output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    """Print Suna setup banner"""
    print(f"""
{Colors.BLUE}{Colors.BOLD}
   ███████╗██╗   ██╗███╗   ██╗ █████╗ 
   ██╔════╝██║   ██║████╗  ██║██╔══██╗
   ███████╗██║   ██║██╔██╗ ██║███████║
   ╚════██║██║   ██║██║╚██╗██║██╔══██║
   ███████║╚██████╔╝██║ ╚████║██║  ██║
   ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝
                                      
   Setup Wizard
{Colors.ENDC}
""")

# PROGRESS_FILE constant is no longer used.
# Functions save_progress, load_progress, and clear_progress are removed.

ENV_DATA_FILE = '.setup_env.json'

def save_env_data(env_data):
    with open(ENV_DATA_FILE, 'w') as f:
        json.dump(env_data, f)

def load_env_data():
    """
    Loads environment data from .setup_env.json if it exists.
    Handles potential old formats and ensures the data structure is current.
    Returns a dictionary with the loaded or default environment settings.
    """
    default_env_data = {
        'supabase': {},
        'daytona': {'SETUP_TYPE': None}, # Ensures SETUP_TYPE is always available for daytona
        'llm': {},
        'search': {},
        'rapidapi': {}
    }
    if os.path.exists(ENV_DATA_FILE):
        try:
            with open(ENV_DATA_FILE, 'r') as f:
                loaded_data = json.load(f)

                # Ensure all top-level keys from default_env_data exist in loaded_data.
                # This handles cases where new sections were added to the setup.
                for key, default_value in default_env_data.items():
                    if key not in loaded_data:
                        loaded_data[key] = default_value

                # Specifically check and upgrade 'daytona' section for compatibility.
                # This ensures 'SETUP_TYPE' exists, which is crucial for new logic.
                daytona_data = loaded_data.get('daytona')
                if not isinstance(daytona_data, dict) or 'SETUP_TYPE' not in daytona_data:
                    old_api_key = None
                    # Try to preserve an old API key if daytona_data was a dict but lacked SETUP_TYPE
                    if isinstance(daytona_data, dict):
                         old_api_key = daytona_data.get('DAYTONA_API_KEY')

                    # Reset daytona to the default structure, then try to populate it.
                    loaded_data['daytona'] = {'SETUP_TYPE': None}
                    if old_api_key:
                         loaded_data['daytona']['DAYTONA_API_KEY'] = old_api_key
                         # If an old API key was found, it's reasonable to assume the setup type was 'daytona'.
                         # This helps migrate users from older .setup_env.json formats.
                         loaded_data['daytona']['SETUP_TYPE'] = 'daytona'
                return loaded_data
        except json.JSONDecodeError:
            print_warning(f"Error decoding {ENV_DATA_FILE}. File might be corrupted. Starting with a fresh configuration.")
            return default_env_data
    return default_env_data

def print_config_safely(config_dict):
    """Prints configuration data, masking sensitive values."""
    sensitive_keywords = ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']
    for key, value in config_dict.items():
        is_sensitive = any(keyword in key.upper() for keyword in sensitive_keywords)
        if is_sensitive and isinstance(value, str) and len(value) > 8:
            masked_value = f"{value[:4]}...{value[-4:]}"
            print(f"  {key}: {masked_value}")
        elif value is not None: # Do not print None values, but print empty strings if they are actual config
            print(f"  {key}: {value}")

def prompt_to_reuse_config(config_name, config_data, specific_check_key=None):
    """
    Prompts the user to reuse existing configuration.
    Returns True if the user wants to reuse, False otherwise.
    """
    has_data = False
    if config_data:
        if specific_check_key: # e.g. 'SETUP_TYPE' for daytona, 'MODEL_TO_USE' for llm
            if config_data.get(specific_check_key):
                has_data = True
        # For dicts, check if any value is truthy, or if it's a non-empty dict for simple cases like supabase
        elif isinstance(config_data, dict) and any(config_data.values()):
            has_data = True
        # For rapidapi, even an empty string for RAPID_API_KEY means it was processed.
        elif config_name == "RapidAPI" and 'RAPID_API_KEY' in config_data:
             has_data = True


    if has_data:
        print_info(f"Found saved {config_name} settings in {Colors.YELLOW}{ENV_DATA_FILE}{Colors.ENDC}:")
        print_config_safely(config_data) # Displays the configuration, masking sensitive parts.
        while True:
            # Clearer prompt for reusing settings
            choice = input(f"Do you want to use these saved {config_name} settings? (yes/no) [default: yes]: ").lower().strip()
            if choice in ['yes', 'y', '']:
                print_success(f"Using saved {config_name} settings.")
                return True
            elif choice in ['no', 'n']:
                return False
            else:
                print_error("Invalid input. Please enter 'yes' or 'no'.")
    return False # No data or user chose not to reuse


def print_step(step_num, total_steps, step_name):
    """Print a step header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}Step {step_num}/{total_steps}: {step_name}{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*50}{Colors.ENDC}\n")

def print_info(message):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ️  {message}{Colors.ENDC}")

def print_success(message):
    """Print success message"""
    print(f"{Colors.GREEN}✅  {message}{Colors.ENDC}")

def print_warning(message):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")

def print_error(message):
    """Print error message"""
    print(f"{Colors.RED}❌  {message}{Colors.ENDC}")

def install_with_winget(package_id, package_name):
    """Attempts to install a package using winget."""
    if not IS_WINDOWS:
        print_info(f"Winget is a Windows tool. Cannot install {package_name} using winget on this OS.")
        return False

    print_info(f"Attempting to install {package_name} using winget...")
    command = [
        'winget', 'install', package_id,
        '--scope', 'user',
        '--accept-source-agreements',
        '--accept-package-agreements',
        '--source', 'winget'
    ]
    try:
        # Using shell=True for winget as it sometimes behaves better.
        # Capture output to prevent it from cluttering the setup script's output too much.
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True, # Capture stdout/stderr
            text=True # Decode output as text
        )
        print_success(f"{package_name} installed successfully via winget.")
        # print_info(f"Winget output:\n{result.stdout}") # Optional: print winget output for debugging
        return True
    except FileNotFoundError:
        print_error(f"Failed to install {package_name}: winget command not found. Please ensure winget is installed and in your PATH.")
        return False
    except subprocess.SubprocessError as e:
        cmd_str = ' '.join(command)
        error_message = f"Failed to install {package_name} using winget. Command: '{cmd_str}'."
        if e.stdout:
            error_message += f"\nWinget stdout:\n{e.stdout}"
        if e.stderr:
            error_message += f"\nWinget stderr:\n{e.stderr}"
        print_error(error_message)
        print_info(f"Please try installing {package_name} manually. You can usually find instructions at the official website for {package_name}.")
        return False

def check_requirements():
    """Check if all required tools are installed"""
    requirements = {
        'git': {'url': 'https://git-scm.com/downloads', 'winget_id': 'Git.Git', 'name': 'Git'},
        'docker': {'url': 'https://docs.docker.com/get-docker/', 'name': 'Docker'},
        'python3': {'url': 'https://www.python.org/downloads/', 'name': 'Python 3'},
        'poetry': {'url': 'https://python-poetry.org/docs/#installation', 'name': 'Poetry'},
        'pip3': {'url': 'https://pip.pypa.io/en/stable/installation/', 'name': 'pip3'},
        'node': {'url': 'https://nodejs.org/en/download/', 'winget_id': 'OpenJS.NodeJS.LTS', 'name': 'Node.js (LTS) and npm'},
        'npm': {'url': 'https://docs.npmjs.com/downloading-and-installing-node-js-and-npm', 'name': 'npm'},
    }
    
    still_missing = [] # Renamed for clarity, stores dicts: {'cmd': cmd, 'url': url, 'name': name}
    
    for cmd, details in requirements.items():
        url = details['url']
        name = details['name']
        cmd_to_check = cmd
        # Removed the outer try block that was here.
        # Check if python3/pip3 for Windows
        if platform.system() == 'Windows' and cmd in ['python3', 'pip3']:
            cmd_to_check = cmd.replace('3', '')
            # cmd_to_check is already set to cmd by default

            try:
                subprocess.run(
                    [cmd_to_check, '--version'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    shell=IS_WINDOWS
                )
                print_success(f"{name} ({cmd}) is installed")
            except (subprocess.SubprocessError, FileNotFoundError):
                print_error(f"{name} ({cmd}) is not installed.")
                # Try to install with winget if applicable
                if IS_WINDOWS and 'winget_id' in details:
                    if install_with_winget(details['winget_id'], name):
                        # Re-check after attempting install
                        try:
                            subprocess.run(
                                [cmd_to_check, '--version'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=True,
                                shell=IS_WINDOWS
                            )
                            print_success(f"{name} ({cmd}) is now installed.")
                            # If node was installed, also check npm
                            if cmd == 'node':
                                try:
                                    subprocess.run(['npm', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, shell=IS_WINDOWS)
                                    print_success("npm (via Node.js) is also installed.")
                                    # Remove npm from still_missing if it was added before node check
                                    still_missing = [m for m in still_missing if m['cmd'] != 'npm']
                                except (subprocess.SubprocessError, FileNotFoundError):
                                    print_error("npm (via Node.js) still not found after Node.js winget install.")
                                    # No need to add npm to still_missing here if node is considered installed.
                                    # However, if the 'npm' check is separate and runs, it will be added.
                        except (subprocess.SubprocessError, FileNotFoundError):
                            print_error(f"{name} ({cmd}) still not found after winget install attempt.")
                            still_missing.append({'cmd': cmd, 'url': url, 'name': name})
                    else:
                        # install_with_winget already printed an error
                        still_missing.append({'cmd': cmd, 'url': url, 'name': name})
                # Handle npm specifically: if node is missing, npm will likely be missing too.
                # The 'npm' check will run separately. If node was installed by winget, npm might be found then.
                elif cmd == 'npm' and any(m['cmd'] == 'node' for m in still_missing):
                    print_info("npm is expected to be missing if Node.js is missing. Will re-check if Node.js gets installed.")
                    still_missing.append({'cmd': cmd, 'url': url, 'name': name})
                else: # Not Windows, or no winget_id, or winget failed
                    still_missing.append({'cmd': cmd, 'url': url, 'name': name})
        # The except (subprocess.SubprocessError, FileNotFoundError) related to the removed outer try is also removed.
        # The inner try-except blocks for subprocess.run and winget checks are preserved.

    if still_missing:
        print_error("\nMissing required tools after automated installation attempts. Please install them manually before continuing:")

        # Deduplicate messages, e.g., if node is missing, don't also list npm separately if it was due to node.
        final_missing_summary = []
        cmds_in_final_summary = set()

        for item in still_missing:
            if item['cmd'] == 'npm' and any(m['cmd'] == 'node' for m in still_missing):
                # If node is missing, npm is implicitly missing. Avoid duplicate message if node message will be shown.
                # However, if node was successfully installed by winget but npm check still failed, then show npm.
                node_installed_by_winget = not any(m['cmd'] == 'node' for m in still_missing)
                if not node_installed_by_winget : # if node is still in missing list
                    continue # skip npm message as node message will cover it.

            if item['cmd'] not in cmds_in_final_summary:
                final_missing_summary.append(item)
                cmds_in_final_summary.add(item['cmd'])

        for item in final_missing_summary:
            print(f"  - {item['name']} ({item['cmd']}): {item['url']}")
        sys.exit(1)
    
    print_success("All critical system requirements appear to be met.")
    return True

def check_docker_running():
    """Check if Docker is running"""
    try:
        result = subprocess.run(
            ['docker', 'info'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            shell=IS_WINDOWS
        )
        print_success("Docker is running")
        return True
    except subprocess.SubprocessError:
        print_error("Docker is installed but not running. Please start Docker and try again.")
        sys.exit(1)

def check_suna_directory():
    """Check if we're in a Suna repository"""
    required_dirs = ['backend', 'frontend']
    required_files = ['README.md', 'docker-compose.yaml']
    
    for directory in required_dirs:
        if not os.path.isdir(directory):
            print_error(f"'{directory}' directory not found. Make sure you're in the Suna repository root.")
            return False
    
    for file in required_files:
        if not os.path.isfile(file):
            print_error(f"'{file}' not found. Make sure you're in the Suna repository root.")
            return False
    
    print_success("Suna repository detected")
    return True

def validate_url(url, allow_empty=False):
    """Validate a URL"""
    if allow_empty and not url:
        return True
    
    pattern = re.compile(
        r'^(?:http|https)://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(pattern.match(url))

def validate_api_key(api_key, allow_empty=False):
    """Validate an API key (basic format check)"""
    if allow_empty and not api_key:
        return True
    
    # Basic check: not empty and at least 10 chars
    return bool(api_key)

def collect_supabase_info():
    """Collect Supabase information"""
    print_info("You'll need to create a Supabase project before continuing")
    print_info("Visit https://supabase.com/dashboard/projects to create one")
    print_info("After creating your project, visit the project settings -> Data API and you'll need to get the following information:")
    print_info("1. Supabase Project URL (e.g., https://abcdefg.supabase.co)")
    print_info("2. Supabase anon key")
    print_info("3. Supabase service role key")
    input("Press Enter to continue once you've created your Supabase project...")
    
    while True:
        supabase_url = input("Enter your Supabase Project URL (e.g., https://abcdefg.supabase.co): ")
        if validate_url(supabase_url):
            break
        print_error("Invalid URL format. Please enter a valid URL.")
    
    while True:
        supabase_anon_key = input("Enter your Supabase anon key: ")
        if validate_api_key(supabase_anon_key):
            break
        print_error("Invalid API key format. It should be at least 10 characters long.")
    
    while True:
        supabase_service_role_key = input("Enter your Supabase service role key: ")
        if validate_api_key(supabase_service_role_key):
            break
        print_error("Invalid API key format. It should be at least 10 characters long.")
    
    return {
        'SUPABASE_URL': supabase_url,
        'SUPABASE_ANON_KEY': supabase_anon_key,
        'SUPABASE_SERVICE_ROLE_KEY': supabase_service_role_key,
    }

def collect_daytona_info():
    """Collects information for the agent execution sandbox, allowing user to choose between Daytona (cloud) or local Docker."""
    print_info("The agent requires a sandbox environment to execute code safely.")
    print_info("You have two options for this sandbox:")
    print(f"{Colors.CYAN}[1] {Colors.GREEN}Daytona Sandbox{Colors.ENDC}")
    print(f"    - Uses a cloud-based service ({Colors.UNDERLINE}https://daytona.io{Colors.ENDC}).")
    print(f"    - Requires a Daytona account and API key.")
    print(f"    - Recommended for ease of use if you have a Daytona account.\n")
    print(f"{Colors.CYAN}[2] {Colors.GREEN}Local Docker Sandbox{Colors.ENDC}")
    print(f"    - Uses Docker running on your own machine.")
    print(f"    - Requires Docker to be installed and running.")
    print(f"    - Good for local development if you prefer not to use a cloud service for the sandbox.\n")

    while True:
        choice = input("Choose your sandbox environment (1 for Daytona, 2 for Local Docker): ")
        if choice in ["1", "2"]:
            break
        print_error("Invalid selection. Please enter '1' for Daytona or '2' for Local Docker.")

    # Branching based on user's choice for sandbox type
    if choice == "1": # User chose Daytona
        print_info("Configuring Suna to use Daytona for the agent sandbox.")
        print_info("You'll need a Daytona account and an API key.")
        print_info(f"Visit {Colors.UNDERLINE}https://app.daytona.io/{Colors.ENDC} to create an account or get your API key.")
        print_info("Additionally, ensure you have the Suna agent image configured in Daytona:")
        print_info(f"  - Image Name: {Colors.YELLOW}kortix/suna:0.1.2.8{Colors.ENDC}")
        print_info(f"  - Entrypoint: {Colors.YELLOW}/usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf{Colors.ENDC}")
        print_info(f"  (These details can be found in {Colors.YELLOW}docs/SELF-HOSTING.md{Colors.ENDC})\n")

        input("Press Enter to continue once you have your Daytona API key and have configured the image...")

        while True:
            daytona_api_key = input("Enter your Daytona API key: ")
            if validate_api_key(daytona_api_key):
                break
            print_error("Invalid API key format. It should be at least 10 characters long.")

        return {
            'SETUP_TYPE': 'daytona', # Explicitly set type for clarity in .env and logic
            'DAYTONA_API_KEY': daytona_api_key,
            'DAYTONA_SERVER_URL': "https://app.daytona.io/api", # Default Daytona server URL
            'DAYTONA_TARGET': "us", # Default Daytona target
        }
    else: # User chose Local Docker
        print_info("Configuring Suna to use a local Docker container for the agent sandbox.")
        print_info(f"Please ensure Docker is installed and running on your system.")
        print_info(f"The sandbox will use the {Colors.YELLOW}kortix/suna:0.1.2.8{Colors.ENDC} Docker image.")
        return {'SETUP_TYPE': 'local_docker'}

def collect_llm_api_keys():
    """Collect LLM API keys for various providers"""
    print_info("You need at least one LLM provider API key to use Suna")
    print_info("Available LLM providers: OpenAI, Anthropic, OpenRouter")
    
    # Display provider selection options
    print(f"\n{Colors.CYAN}Select LLM providers to configure:{Colors.ENDC}")
    print(f"{Colors.CYAN}[1] {Colors.GREEN}OpenAI{Colors.ENDC}")
    print(f"{Colors.CYAN}[2] {Colors.GREEN}Anthropic{Colors.ENDC}")
    print(f"{Colors.CYAN}[3] {Colors.GREEN}OpenRouter{Colors.ENDC} {Colors.CYAN}(access to multiple models){Colors.ENDC}")
    print(f"{Colors.CYAN}[4] {Colors.GREEN}Ollama{Colors.ENDC} {Colors.CYAN}(local models, ensure OLLAMA_API_BASE is set){Colors.ENDC}")
    print(f"{Colors.CYAN}Enter numbers separated by commas (e.g., 1,2,3,4){Colors.ENDC}\n")

    while True:
        providers_input = input("Select providers (required, at least one): ")
        selected_providers = []
        
        try:
            # Parse the input, handle both comma-separated and space-separated
            provider_numbers = [int(p.strip()) for p in providers_input.replace(',', ' ').split()]
            
            for num in provider_numbers:
                if num == 1:
                    selected_providers.append('OPENAI')
                elif num == 2:
                    selected_providers.append('ANTHROPIC')
                elif num == 3:
                    selected_providers.append('OPENROUTER')
                elif num == 4:
                    selected_providers.append('OLLAMA')
            
            if selected_providers:
                break
            else:
                print_error("Please select at least one provider.")
        except ValueError:
            print_error("Invalid input. Please enter provider numbers (e.g., 1,2,3).")

    # Collect API keys for selected providers
    api_keys = {}
    # model_info = {} # model_info was used to store a single 'default_model', this will be handled differently.
    
    # Store chosen models for each provider temporarily
    chosen_anthropic_model = None
    chosen_openai_model = None
    chosen_ollama_model = None
    chosen_openrouter_model = None

    # Model aliases for reference
    model_aliases = {
        'OPENAI': ['openai/gpt-4o', 'openai/gpt-4o-mini'],
        'ANTHROPIC': ['anthropic/claude-3-7-sonnet-latest', 'anthropic/claude-3-5-sonnet-latest'],
        'OPENROUTER': ['openrouter/google/gemini-2.5-pro-preview', 'openrouter/deepseek/deepseek-chat-v3-0324:free', 'openrouter/openai/gpt-4o-2024-11-20'],
        'OLLAMA': ['ollama_chat/llama3.1', 'ollama_chat/mistral', 'ollama_chat/codellama'],
    }
    
    for provider in selected_providers:
        print_info(f"\nConfiguring {provider}")
        
        if provider == 'OLLAMA':
            print_info("Ollama selected. Ensure your Ollama server is running.")
            print_info("OLLAMA_API_BASE will be set in backend/.env (defaults to http://localhost:11434 if not otherwise specified by your environment).")
            api_keys['OLLAMA_ENABLED'] = True # Mark Ollama as selected

            print(f"\n{Colors.CYAN}Recommended Ollama models (ensure these are available in your Ollama server):{Colors.ENDC}")
            for i, model in enumerate(model_aliases['OLLAMA'], 1):
                print(f"{Colors.CYAN}[{i}] {Colors.GREEN}{model}{Colors.ENDC}")
            print(f"{Colors.CYAN}[{len(model_aliases['OLLAMA']) + 1}] {Colors.GREEN}Enter a custom Ollama model ID{Colors.ENDC}")

            ollama_model_choice_input = input(f"Select default Ollama model (1-{len(model_aliases['OLLAMA']) + 1}) or press Enter for '{model_aliases['OLLAMA'][0]}': ").strip()

            if not ollama_model_choice_input:
                chosen_ollama_model = model_aliases['OLLAMA'][0]
            elif ollama_model_choice_input.isdigit():
                choice_num = int(ollama_model_choice_input)
                if 1 <= choice_num <= len(model_aliases['OLLAMA']):
                    chosen_ollama_model = model_aliases['OLLAMA'][choice_num - 1]
                elif choice_num == len(model_aliases['OLLAMA']) + 1:
                    custom_model_id = input("Enter your custom Ollama model ID (e.g., ollama_chat/my-custom-model): ").strip()
                    if custom_model_id: # Basic validation: not empty
                        chosen_ollama_model = custom_model_id
                    else:
                        chosen_ollama_model = model_aliases['OLLAMA'][0]
                        print_warning(f"No custom model entered, using default: {chosen_ollama_model}")
                else:
                    chosen_ollama_model = model_aliases['OLLAMA'][0]
                    print_warning(f"Invalid selection, using default: {chosen_ollama_model}")
            else: # User might have typed a model name directly
                chosen_ollama_model = ollama_model_choice_input

            api_keys['OLLAMA_DEFAULT_MODEL'] = chosen_ollama_model # Store it temporarily
            print_info(f"Selected Ollama model: {chosen_ollama_model}")

        elif provider == 'OPENAI':
            while True:
                api_key = input("Enter your OpenAI API key: ")
                if validate_api_key(api_key):
                    api_keys['OPENAI_API_KEY'] = api_key
                    
                    # Recommend default model
                    print(f"\n{Colors.CYAN}Recommended OpenAI models:{Colors.ENDC}")
                    for i, model in enumerate(model_aliases['OPENAI'], 1):
                        print(f"{Colors.CYAN}[{i}] {Colors.GREEN}{model}{Colors.ENDC}")
                    
                    model_choice_input = input(f"Select OpenAI model (1-{len(model_aliases['OPENAI'])}) or press Enter for '{model_aliases['OPENAI'][0]}': ").strip()
                    if not model_choice_input:
                        chosen_openai_model = model_aliases['OPENAI'][0]
                    elif model_choice_input.isdigit() and 1 <= int(model_choice_input) <= len(model_aliases['OPENAI']):
                        chosen_openai_model = model_aliases['OPENAI'][int(model_choice_input) - 1]
                    else:
                        chosen_openai_model = model_aliases['OPENAI'][0]
                        print_warning(f"Invalid selection, using default: {chosen_openai_model}")
                    print_info(f"Selected OpenAI model: {chosen_openai_model}")
                    break
                print_error("Invalid API key format. It should be at least 10 characters long.")
        
        elif provider == 'ANTHROPIC':
            while True:
                api_key = input("Enter your Anthropic API key: ")
                if validate_api_key(api_key):
                    api_keys['ANTHROPIC_API_KEY'] = api_key
                    
                    # Recommend default model
                    print(f"\n{Colors.CYAN}Recommended Anthropic models:{Colors.ENDC}")
                    for i, model in enumerate(model_aliases['ANTHROPIC'], 1):
                        print(f"{Colors.CYAN}[{i}] {Colors.GREEN}{model}{Colors.ENDC}")
                    
                    model_choice_input = input(f"Select Anthropic model (1-{len(model_aliases['ANTHROPIC'])}) or press Enter for '{model_aliases['ANTHROPIC'][0]}': ").strip()
                    if not model_choice_input or model_choice_input == '1':
                        chosen_anthropic_model = model_aliases['ANTHROPIC'][0]
                    elif model_choice_input.isdigit() and 1 <= int(model_choice_input) <= len(model_aliases['ANTHROPIC']):
                        chosen_anthropic_model = model_aliases['ANTHROPIC'][int(model_choice_input) - 1]
                    else:
                        chosen_anthropic_model = model_aliases['ANTHROPIC'][0]
                        print_warning(f"Invalid selection, using default: {chosen_anthropic_model}")
                    print_info(f"Selected Anthropic model: {chosen_anthropic_model}")
                    break
                print_error("Invalid API key format. It should be at least 10 characters long.")
        
        elif provider == 'OPENROUTER':
            while True:
                api_key = input("Enter your OpenRouter API key: ")
                if validate_api_key(api_key):
                    api_keys['OPENROUTER_API_KEY'] = api_key
                    api_keys['OPENROUTER_API_BASE'] = 'https://openrouter.ai/api/v1'

                    # Recommend default model
                    print(f"\n{Colors.CYAN}Recommended OpenRouter models:{Colors.ENDC}")
                    for i, model in enumerate(model_aliases['OPENROUTER'], 1):
                        print(f"{Colors.CYAN}[{i}] {Colors.GREEN}{model}{Colors.ENDC}")
                    
                    model_choice_input = input(f"Select OpenRouter model (1-{len(model_aliases['OPENROUTER'])}) or press Enter for '{model_aliases['OPENROUTER'][0]}': ").strip()
                    if not model_choice_input or model_choice_input == '1':
                        chosen_openrouter_model = model_aliases['OPENROUTER'][0]
                    elif model_choice_input.isdigit() and 1 <= int(model_choice_input) <= len(model_aliases['OPENROUTER']):
                        chosen_openrouter_model = model_aliases['OPENROUTER'][int(model_choice_input) - 1]
                    else:
                        chosen_openrouter_model = model_aliases['OPENROUTER'][0]
                        print_warning(f"Invalid selection, using default: {chosen_openrouter_model}")
                    print_info(f"Selected OpenRouter model: {chosen_openrouter_model}")
                    break
                print_error("Invalid API key format. It should be at least 10 characters long.")
        
    # Determine the final MODEL_TO_USE based on priority and user selections
    final_default_model = None

    if chosen_anthropic_model:
        final_default_model = chosen_anthropic_model
    elif chosen_openai_model:
        final_default_model = chosen_openai_model
    elif chosen_ollama_model: # This is from api_keys['OLLAMA_DEFAULT_MODEL'] which was set if Ollama was chosen
        final_default_model = chosen_ollama_model
    elif chosen_openrouter_model:
        final_default_model = chosen_openrouter_model
    else:
        # Fallback if no specific model was chosen for any *selected* provider,
        # but providers *were* selected. Pick first from aliases of selected providers based on priority.
        if 'ANTHROPIC_API_KEY' in api_keys:
            final_default_model = model_aliases['ANTHROPIC'][0]
        elif 'OPENAI_API_KEY' in api_keys:
            final_default_model = model_aliases['OPENAI'][0]
        elif 'OLLAMA_ENABLED' in api_keys: # Check if Ollama was selected at all
             # api_keys['OLLAMA_DEFAULT_MODEL'] should have been set if Ollama was selected.
             # This is a fallback if it somehow wasn't (e.g. user skipped prompt for Ollama).
            final_default_model = api_keys.get('OLLAMA_DEFAULT_MODEL', model_aliases['OLLAMA'][0])
        elif 'OPENROUTER_API_KEY' in api_keys:
            final_default_model = model_aliases['OPENROUTER'][0]

    if final_default_model:
        print_success(f"Using {final_default_model} as the default model for MODEL_TO_USE")
        api_keys['MODEL_TO_USE'] = final_default_model
    else:
        # This case should be rare given the selection requirement at the beginning.
        print_error("Could not determine a default model. This should not happen if at least one provider is selected.")
        # As a last resort, if this state is reached:
        api_keys['MODEL_TO_USE'] = 'anthropic/claude-3-7-sonnet-latest' # A failsafe default
        print_warning(f"Setting a failsafe default model: {api_keys['MODEL_TO_USE']}. Please review your .env file.")

    # Remove OLLAMA_DEFAULT_MODEL from api_keys if it exists, as it's temporary for this function's logic
    api_keys.pop('OLLAMA_DEFAULT_MODEL', None)
    
    return api_keys

def collect_search_api_keys():
    """Collect search API keys (now required, not optional)"""
    print_info("You'll need to obtain API keys for search and web scraping")
    print_info("Visit https://tavily.com/ to get a Tavily API key")
    print_info("Visit https://firecrawl.dev/ to get a Firecrawl API key")
    
    while True:
        tavily_api_key = input("Enter your Tavily API key: ")
        if validate_api_key(tavily_api_key):
            break
        print_error("Invalid API key format. It should be at least 10 characters long.")
    
    while True:
        firecrawl_api_key = input("Enter your Firecrawl API key: ")
        if validate_api_key(firecrawl_api_key):
            break
        print_error("Invalid API key format. It should be at least 10 characters long.")
    
    # Ask if user is self-hosting Firecrawl
    is_self_hosted = input("Are you self-hosting Firecrawl? (y/n): ").lower().strip() == 'y'
    firecrawl_url = "https://api.firecrawl.dev"  # Default URL
    
    if is_self_hosted:
        while True:
            custom_url = input("Enter your Firecrawl URL (e.g., https://your-firecrawl-instance.com): ")
            if validate_url(custom_url):
                firecrawl_url = custom_url
                break
            print_error("Invalid URL format. Please enter a valid URL.")
    
    return {
        'TAVILY_API_KEY': tavily_api_key,
        'FIRECRAWL_API_KEY': firecrawl_api_key,
        'FIRECRAWL_URL': firecrawl_url,
    }

def collect_rapidapi_keys():
    """Collect RapidAPI key (optional)"""
    print_info("To enable API services like LinkedIn, and others, you'll need a RapidAPI key")
    print_info("Each service requires individual activation in your RapidAPI account:")
    print_info("1. Locate the service's `base_url` in its corresponding file (e.g., https://linkedin-data-scraper.p.rapidapi.com in backend/agent/tools/data_providers/LinkedinProvider.py)")
    print_info("2. Visit that specific API on the RapidAPI marketplace")
    print_info("3. Subscribe to th`e service (many offer free tiers with limited requests)")
    print_info("4. Once subscribed, the service will be available to your agent through the API Services tool")
    print_info("A RapidAPI key is optional for API services like LinkedIn")
    print_info("Visit https://rapidapi.com/ to get your API key if needed")
    print_info("You can leave this blank and add it later if desired")
    
    rapid_api_key = input("Enter your RapidAPI key (optional, press Enter to skip): ")
    
    # Allow empty key
    if not rapid_api_key:
        print_info("Skipping RapidAPI key setup. You can add it later if needed.")
    else:
        # Validate if not empty
        if not validate_api_key(rapid_api_key, allow_empty=True):
            print_warning("The API key format seems invalid, but continuing anyway.")
    
    return {
        'RAPID_API_KEY': rapid_api_key,
    }

def configure_backend_env(env_vars, use_docker=True):
    """Configure backend .env file"""
    env_path = os.path.join('backend', '.env')
    
    # Redis configuration (based on deployment method)
    redis_host = 'redis' if use_docker else 'localhost'
    redis_config = {
        'REDIS_HOST': redis_host,
        'REDIS_PORT': '6379',
        'REDIS_PASSWORD': '',
        'REDIS_SSL': 'false',
    }

    # RabbitMQ configuration (based on deployment method)
    rabbitmq_host = 'rabbitmq' if use_docker else 'localhost'
    rabbitmq_config = {
        'RABBITMQ_HOST': rabbitmq_host,
        'RABBITMQ_PORT': '5672',
    }
    
    # Organize all configuration
    all_config = {}
    
    # Create a string with the formatted content
    env_content = """# Generated by Suna setup script

# Environment Mode
# Valid values: local, staging, production
ENV_MODE=local

#DATABASE
"""

    # Supabase section
    for key, value in env_vars['supabase'].items():
        env_content += f"{key}={value}\n"
    
    # Redis section
    env_content += "\n# REDIS\n"
    for key, value in redis_config.items():
        env_content += f"{key}={value}\n"
    
    # RabbitMQ section
    env_content += "\n# RABBITMQ\n"
    for key, value in rabbitmq_config.items():
        env_content += f"{key}={value}\n"
    
    # LLM section
    env_content += "\n# LLM Providers:\n"
    # Add empty values for all LLM providers we support
    # OLLAMA_API_KEY is not used by LiteLLM typically, but OLLAMA_API_BASE is.
    # OLLAMA_ENABLED was a temporary marker in collect_llm_api_keys.
    # config.py handles OLLAMA_API_BASE default.
    all_llm_keys = ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GROQ_API_KEY', 'OPENROUTER_API_KEY', 'MODEL_TO_USE', 'OLLAMA_API_BASE'] # Added OLLAMA_API_BASE
    # Add AWS keys separately
    aws_keys = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION_NAME']
    
    # Process provided LLM keys
    llm_env_values = env_vars['llm'].copy() # Work on a copy

    # If Ollama was selected, ensure OLLAMA_API_BASE gets a value for .env
    # Even if it's empty, so config.py can load it (and apply default if empty)
    if llm_env_values.pop('OLLAMA_ENABLED', False): # Remove the temporary marker
        if 'OLLAMA_API_BASE' not in llm_env_values: # If not explicitly set (e.g. future prompt)
             llm_env_values['OLLAMA_API_BASE'] = '' # Add it as empty, config.py will use default

    # First add the keys that were provided or derived
    for key, value in llm_env_values.items():
        if key in all_llm_keys: # Check if it's a recognized key
            env_content += f"{key}={value}\n"
            if key in all_llm_keys: # Remove from list to avoid adding it again as empty
                all_llm_keys.remove(key)
    
    # Add empty values for any remaining LLM keys that weren't provided
    for key in all_llm_keys:
        # GROQ_API_KEY is often not set, so ensure it's written if not present
        # OLLAMA_API_BASE will be written if it was in llm_env_values (e.g. empty string)
        # or if it's still in all_llm_keys (meaning it wasn't in llm_env_values)
        if key == 'OLLAMA_API_BASE' and 'OLLAMA_API_BASE' not in llm_env_values:
             env_content += f"{key}=\n" # Will use default from config.py
        elif key != 'OLLAMA_API_BASE': # Avoid double-adding OLLAMA_API_BASE
            env_content += f"{key}=\n"

    # AWS section
    env_content += "\n# AWS Bedrock\n"
    for key in aws_keys:
        value = llm_env_values.get(key, '') # Use llm_env_values which is the processed set
        env_content += f"{key}={value}\n"
    
    # Additional OpenRouter params
    if 'OR_SITE_URL' in llm_env_values or 'OR_APP_NAME' in llm_env_values:
        env_content += "\n# OpenRouter Additional Settings\n"
        if 'OR_SITE_URL' in llm_env_values:
            env_content += f"OR_SITE_URL={llm_env_values['OR_SITE_URL']}\n"
        if 'OR_APP_NAME' in llm_env_values:
            env_content += f"OR_APP_NAME={llm_env_values['OR_APP_NAME']}\n"
    
    # DATA APIs section
    env_content += "\n# DATA APIS\n"
    for key, value in env_vars['rapidapi'].items():
        env_content += f"{key}={value}\n"
    
    # Web search section
    env_content += "\n# WEB SEARCH\n"
    tavily_key = env_vars['search'].get('TAVILY_API_KEY', '')
    env_content += f"TAVILY_API_KEY={tavily_key}\n"
    
    # Web scrape section
    env_content += "\n# WEB SCRAPE\n"
    firecrawl_key = env_vars['search'].get('FIRECRAWL_API_KEY', '')
    firecrawl_url = env_vars['search'].get('FIRECRAWL_URL', '')
    env_content += f"FIRECRAWL_API_KEY={firecrawl_key}\n"
    env_content += f"FIRECRAWL_URL={firecrawl_url}\n"
    
    # Sandbox container provider section
    # The SANDBOX_TYPE variable determines whether the agent executes code
    # in a Daytona cloud sandbox or a locally running Docker container.
    # This is based on the user's choice in the `collect_daytona_info` step.
    env_content += "\n# Sandbox container provider:\n"
    daytona_config = env_vars.get('daytona', {}) # Get the 'daytona' dictionary, or empty if not set
    setup_type = daytona_config.get('SETUP_TYPE') # Get the chosen setup type ('daytona' or 'local_docker')

    if setup_type == 'daytona':
        # If Daytona is chosen, set SANDBOX_TYPE and related Daytona variables
        env_content += "SANDBOX_TYPE=daytona\n"
        env_content += f"DAYTONA_API_KEY={daytona_config.get('DAYTONA_API_KEY', '')}\n"
        env_content += f"DAYTONA_SERVER_URL={daytona_config.get('DAYTONA_SERVER_URL', 'https://app.daytona.io/api')}\n" # Default URL
        env_content += f"DAYTONA_TARGET={daytona_config.get('DAYTONA_TARGET', 'us')}\n" # Default target
    elif setup_type == 'local_docker':
        # If local Docker is chosen, only SANDBOX_TYPE is needed
        env_content += "SANDBOX_TYPE=local_docker\n"
    else:
        # Fallback if SETUP_TYPE is somehow not set or has an unexpected value.
        # Defaulting to 'local_docker' is a safe option, assuming Docker is available.
        # This situation should ideally be prevented by earlier validation/collection steps.
        print_warning(f"Sandbox SETUP_TYPE is undefined or invalid ('{setup_type}'). Defaulting to 'local_docker'.")
        env_content += "SANDBOX_TYPE=local_docker\n"

    # Add next public URL at the end
    env_content += f"NEXT_PUBLIC_URL=http://localhost:3000\n"
    
    # Write to file
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print_success(f"Backend .env file created at {env_path}")
    print_info(f"Redis host is set to: {redis_host}")
    print_info(f"RabbitMQ host is set to: {rabbitmq_host}")

def configure_frontend_env(env_vars, use_docker=True):
    """Configure frontend .env.local file"""
    env_path = os.path.join('frontend', '.env.local')
    
    # Use the appropriate backend URL based on start method
    backend_url = "http://localhost:8000/api"

    config = {
        'NEXT_PUBLIC_SUPABASE_URL': env_vars['supabase']['SUPABASE_URL'],
        'NEXT_PUBLIC_SUPABASE_ANON_KEY': env_vars['supabase']['SUPABASE_ANON_KEY'],
        'NEXT_PUBLIC_BACKEND_URL': backend_url,
        'NEXT_PUBLIC_URL': 'http://localhost:3000',
        'NEXT_PUBLIC_ENV_MODE': 'LOCAL',
    }

    # Write to file
    with open(env_path, 'w') as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")
    
    print_success(f"Frontend .env.local file created at {env_path}")
    print_info(f"Backend URL is set to: {backend_url}")

def setup_supabase():
    """Setup Supabase database"""
    print_info("Setting up Supabase database...")
    
    # Check if the Supabase CLI is installed
    try:
        subprocess.run(
            ['supabase', '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            shell=IS_WINDOWS
        )
        print_success("Supabase CLI is installed.")
    except (subprocess.SubprocessError, FileNotFoundError):
        print_warning("Supabase CLI not found or version check failed. Attempting to install/verify with winget...")
        if IS_WINDOWS and install_with_winget("Supabase.CLI", "Supabase CLI"):
            try:
                # Re-check after attempting install
                subprocess.run(
                    ['supabase', '--version'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    shell=IS_WINDOWS # IS_WINDOWS is correct here
                )
                print_success("Supabase CLI successfully installed/verified via winget.")
            except (subprocess.SubprocessError, FileNotFoundError):
                print_error("Supabase CLI still not found or version check failed after winget attempt.")
                print_info("Please install it manually by following instructions at https://supabase.com/docs/guides/cli/getting-started")
                print_info("After installing, run this setup again.")
                sys.exit(1)
        else:
            # install_with_winget prints its own error if it fails or not on Windows.
            # If not on Windows, or winget failed, print the manual install instructions.
            if not IS_WINDOWS: # Clarify message if not on Windows (winget was skipped)
                 print_error("Supabase CLI is not installed (winget not applicable on this OS).")
            else: # Winget was attempted but failed
                 print_error("Supabase CLI installation via winget failed.")
            print_info("Please install Supabase CLI manually by following instructions at https://supabase.com/docs/guides/cli/getting-started")
            print_info("After installing, run this setup again.")
            sys.exit(1)
    
    # Extract project reference from Supabase URL
    supabase_url = os.environ.get('SUPABASE_URL')
    if not supabase_url:
        # Get from main function if environment variable not set
        env_path = os.path.join('backend', '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('SUPABASE_URL='):
                        supabase_url = line.strip().split('=', 1)[1]
                        break

    project_ref = None
    if supabase_url:
        # Extract project reference from URL (format: https://[project_ref].supabase.co)
        match = re.search(r'https://([^.]+)\.supabase\.co', supabase_url)
        if match:
            project_ref = match.group(1)
            print_success(f"Extracted project reference '{project_ref}' from your Supabase URL")
    
    # If extraction failed, ask the user
    if not project_ref:
        print_info("Could not extract project reference from Supabase URL")
        print_info("Get your Supabase project reference from the Supabase dashboard")
        print_info("It's the portion after 'https://' and before '.supabase.co' in your project URL")
        project_ref = input("Enter your Supabase project reference: ")
    
    # Change the working directory to backend
    backend_dir = os.path.join(os.getcwd(), 'backend')
    print_info(f"Changing to backend directory: {backend_dir}")
    
    try:
        # Login to Supabase CLI (interactive)
        print_info("Logging into Supabase CLI...")
        subprocess.run(['supabase', 'login'], check=True, shell=IS_WINDOWS)
        
        # Link to project
        print_info(f"Linking to Supabase project {project_ref}...")
        subprocess.run(
            ['supabase', 'link', '--project-ref', project_ref],
            cwd=backend_dir,
            check=True,
            shell=IS_WINDOWS
        )
        
        # Push database migrations
        print_info("Pushing database migrations...")
        subprocess.run(
            ['supabase', 'db', 'push'],
            cwd=backend_dir,
            check=True,
            shell=IS_WINDOWS
        )
        
        print_success("Supabase database setup completed")
        
        # Reminder for manual step
        print_warning("IMPORTANT: You need to manually expose the 'basejump' schema in Supabase")
        print_info("Go to the Supabase web platform -> choose your project -> Project Settings -> Data API")
        print_info("In the 'Exposed Schema' section, add 'basejump' if not already there")
        input("Press Enter once you've completed this step...")
        
    except subprocess.SubprocessError as e:
        print_error(f"Failed to setup Supabase: {e}")
        sys.exit(1)

def install_dependencies():
    """Install frontend and backend dependencies"""
    print_info("Installing required dependencies...")
    
    try:
        # Install frontend dependencies
        print_info("Installing frontend dependencies...")
        subprocess.run(
            ['npm', 'install'], 
            cwd='frontend',
            check=True,
            shell=IS_WINDOWS
        )
        print_success("Frontend dependencies installed successfully")
        
        # Configure poetry for local virtual environment
        print_info("Configuring poetry for local virtual environment...")
        try:
            # Configure poetry for local virtual environment (optional optimization)
            print_info("Attempting to configure Poetry for local virtual environment (optional)...")
            # Run first command
            proc1 = subprocess.run(
                ['poetry', 'config', 'virtualenvs.create', 'true', '--local'],
                cwd='backend',
                shell=IS_WINDOWS,
                capture_output=True, text=True, check=False # Changed check to False
            )
            # Run second command
            proc2 = subprocess.run(
                ['poetry', 'config', 'virtualenvs.in-project', 'true', '--local'],
                cwd='backend',
                shell=IS_WINDOWS,
                capture_output=True, text=True, check=False # Changed check to False
            )

            if proc1.returncode == 0 and proc2.returncode == 0:
                print_success("Poetry successfully configured for local virtual environment creation and in-project storage.")
            else:
                print_warning("Could not automatically configure Poetry's virtualenv settings (virtualenvs.create true --local / virtualenvs.in-project true --local).")
                print_info("This is an optional optimization and setup will continue.")
                if proc1.returncode != 0:
                    print_warning(f"  virtualenvs.create command failed. Stderr: {proc1.stderr.strip()}")
                if proc2.returncode != 0:
                    print_warning(f"  virtualenvs.in-project command failed. Stderr: {proc2.stderr.strip()}")
        except Exception as e: # Catch any other unexpected error during these specific subprocess calls
            print_warning(f"An unexpected error occurred while trying to configure poetry for local virtualenvs: {e}")
            print_info("This is an optional optimization and setup will continue.")

        # Lock dependencies
        print_info("Locking dependencies...")
        subprocess.run(
            ['poetry', 'lock'],
            cwd='backend',
            check=True,
            shell=IS_WINDOWS
        )
        # Install backend dependencies
        print_info("Installing backend dependencies...")
        subprocess.run(
            ['poetry', 'install'], 
            cwd='backend',
            check=True,
            shell=IS_WINDOWS
        )
        print_success("Backend dependencies installed successfully")
        
        return True
    except subprocess.SubprocessError as e:
        print_error(f"Failed to install dependencies: {e}")
        print_info("You may need to install them manually.")
        return False

def start_suna():
    """Start Suna using Docker Compose or manual startup"""
    print_info("You can start Suna using either Docker Compose or by manually starting the frontend, backend and worker.")

    print(f"\n{Colors.CYAN}How would you like to start Suna?{Colors.ENDC}")
    print(f"{Colors.CYAN}[1] {Colors.GREEN}Docker Compose{Colors.ENDC} {Colors.CYAN}(recommended, starts all services){Colors.ENDC}")
    print(f"{Colors.CYAN}[2] {Colors.GREEN}Manual startup{Colors.ENDC} {Colors.CYAN}(requires Redis, RabbitMQ & separate terminals){Colors.ENDC}\n")
    
    while True:
        start_method = input("Enter your choice (1 or 2): ")
        if start_method in ["1", "2"]:
            break
        print_error("Invalid selection. Please enter '1' for Docker Compose or '2' for Manual startup.")
    
    use_docker = start_method == "1"
    
    if use_docker:
        print_info("Starting Suna with Docker Compose...")
        
        try:
            # TODO: uncomment when we have pre-built images on Docker Hub or GHCR
            # GitHub repository environment variable setup
            # github_repo = None
            
            # print(f"\n{Colors.CYAN}Do you want to use pre-built images or build locally?{Colors.ENDC}")
            # print(f"{Colors.CYAN}[1] {Colors.GREEN}Pre-built images{Colors.ENDC} {Colors.CYAN}(faster){Colors.ENDC}")
            # print(f"{Colors.CYAN}[2] {Colors.GREEN}Build locally{Colors.ENDC} {Colors.CYAN}(customizable){Colors.ENDC}\n")
            
            # while True:
            #     build_choice = input("Enter your choice (1 or 2): ")
            #     if build_choice in ["1", "2"]:
            #         break
            #     print_error("Invalid selection. Please enter '1' for pre-built images or '2' for building locally.")
                
            # use_prebuilt = build_choice == "1"
            
            # if use_prebuilt:
            #     # Get GitHub repository name from user
            #     print_info("For pre-built images, you need to specify a GitHub repository name")
            #     print_info("Example format: your-github-username/repo-name")
                
            #     github_repo = input("Enter GitHub repository name: ")
            #     if not github_repo or "/" not in github_repo:
            #         print_warning("Invalid GitHub repository format. Using a default value.")
            #         # Create a random GitHub repository name as fallback
            #         random_name = ''.join(random.choices(string.ascii_lowercase, k=8))
            #         github_repo = f"user/{random_name}"
                
            #     # Set the environment variable
            #     os.environ["GITHUB_REPOSITORY"] = github_repo
            #     print_info(f"Using GitHub repository: {github_repo}")
                
            #     # Start with pre-built images
            #     print_info("Using pre-built images...")
            #     subprocess.run(['docker', 'compose', '-f', 'docker-compose.ghcr.yaml', 'up', '-d'], check=True)
            # else:
            #     # Start with docker-compose (build images locally)
            #     print_info("Building images locally...")
            #     subprocess.run(['docker', 'compose', 'up', '-d'], check=True)

            print_info("Building images locally...")
            subprocess.run(['docker', 'compose', 'up', '-d', '--build'], check=True, shell=IS_WINDOWS)

            # Wait for services to be ready
            print_info("Waiting for services to start...")
            time.sleep(10)  # Give services some time to start
            
            # Check if services are running
            result = subprocess.run(
                ['docker', 'compose', 'ps', '-q'],
                capture_output=True,
                text=True,
                shell=IS_WINDOWS
            )
            
            if "backend" in result.stdout and "frontend" in result.stdout:
                print_success("Suna services are up and running!")
            else:
                print_warning("Some services might not be running correctly. Check 'docker compose ps' for details.")
            
        except subprocess.SubprocessError as e:
            print_error(f"Failed to start Suna: {e}")
            sys.exit(1)
            
        return use_docker
    else:
        print_info("For manual startup, you'll need to:")
        print_info("1. Start Redis and RabbitMQ in Docker (required for the backend)")
        print_info("2. Start the frontend with npm run dev")
        print_info("3. Start the backend with poetry run python3.11 api.py")
        print_info("4. Start the worker with poetry run python3.11 -m dramatiq run_agent_background")
        print_warning("Note: Redis and RabbitMQ must be running before starting the backend")
        print_info("Detailed instructions will be provided at the end of setup")
        
        return use_docker

def final_instructions(use_docker=True, env_vars=None):
    """Show final instructions"""
    print(f"\n{Colors.GREEN}{Colors.BOLD}✨ Suna Setup Complete! ✨{Colors.ENDC}\n")
    
    # Display LLM configuration info if available
    if env_vars and 'llm' in env_vars and 'MODEL_TO_USE' in env_vars['llm']:
        default_model = env_vars['llm']['MODEL_TO_USE']
        print_info(f"Suna is configured to use {Colors.GREEN}{default_model}{Colors.ENDC} as the default LLM model.")
    
    # Display sandbox type if available
    if env_vars and 'daytona' in env_vars and 'SETUP_TYPE' in env_vars['daytona']:
        sandbox_type = env_vars['daytona']['SETUP_TYPE']
        if sandbox_type == 'daytona':
            print_info(f"Agent sandbox is configured to use {Colors.GREEN}Daytona (cloud sandbox){Colors.ENDC}.")
        elif sandbox_type == 'local_docker':
            print_info(f"Agent sandbox is configured to use {Colors.GREEN}Local Docker{Colors.ENDC}.")
        print_info(f"Refer to {Colors.YELLOW}docs/SELF-HOSTING.md{Colors.ENDC} for more details on your setup.")

    if use_docker:
        print_info("Your Suna instance (backend, frontend, etc.) is now running via Docker Compose!")
        print_info("Access it at: http://localhost:3000")
        print_info("Create an account using Supabase authentication to start using Suna")
        print("\nUseful Docker commands:")
        print(f"{Colors.CYAN}  docker compose ps{Colors.ENDC}         - Check the status of Suna services")
        print(f"{Colors.CYAN}  docker compose logs{Colors.ENDC}       - View logs from all services")
        print(f"{Colors.CYAN}  docker compose logs -f{Colors.ENDC}    - Follow logs from all services")
        print(f"{Colors.CYAN}  docker compose down{Colors.ENDC}       - Stop Suna services")
        print(f"{Colors.CYAN}  docker compose up -d{Colors.ENDC}      - Start Suna services (after they've been stopped)")
    else:
        print_info("Suna setup is complete but services are not running yet.")
        print_info("To start Suna, you need to:")
        
        print_info("1. Start Redis and RabbitMQ (required for backend):")
        print(f"{Colors.CYAN}    cd backend")
        print(f"    docker compose up redis rabbitmq -d{Colors.ENDC}")
        
        print_info("2. In one terminal:")
        print(f"{Colors.CYAN}    cd frontend")
        print(f"    npm run dev{Colors.ENDC}")
        
        print_info("3. In another terminal:")
        print(f"{Colors.CYAN}    cd backend")
        print(f"    poetry run python3.11 api.py{Colors.ENDC}")
        
        print_info("3. In one more terminal:")
        print(f"{Colors.CYAN}    cd backend")
        print(f"    poetry run python3.11 -m dramatiq run_agent_background{Colors.ENDC}")
        
        print_info("4. Once all services are running, access Suna at: http://localhost:3000")
        print_info("5. Create an account using Supabase authentication to start using Suna")

# Then update your main() function as follows:

def main():
    total_steps = 8  # Total number of steps remains for display purposes
    current_step = 1 # Initialize current_step to 1

    print_banner()
    # General introduction to the setup wizard.
    print(f"Welcome to the Suna Setup Wizard!")
    print("This script will guide you through configuring the Suna application.")
    print(f"It will help you set up API keys, database connections, and other essential settings.")
    print(f"Previously entered data (if any) will be loaded from {Colors.YELLOW}{ENV_DATA_FILE}{Colors.ENDC} and you'll be asked to confirm its use.\n")

    # Load existing environment data or defaults. This supports resuming setup.
    env_vars = load_env_data()

    # Step 1: Check system requirements (Docker, Git, Python, Node, etc.)
    print_step(current_step, total_steps, "Checking System Requirements")
    if not check_requirements(): # Exits if requirements are not met.
        sys.exit(1)
    if not check_docker_running(): # Exits if Docker is not running.
            sys.exit(1)
    if not check_suna_directory(): # Exits if not in the correct Suna directory.
        print_error("This setup script must be run from the Suna repository root directory.")
        sys.exit(1)
    current_step += 1

    # Step 2: Collect Supabase information (database and authentication)
    print_step(current_step, total_steps, "Collecting Supabase Information (Database & Auth)")
    # Prompt user to reuse existing Supabase config if available.
    if not prompt_to_reuse_config("Supabase", env_vars.get('supabase'), specific_check_key='SUPABASE_URL'):
        env_vars['supabase'] = collect_supabase_info()

    # Critical check: SUPABASE_URL is required for subsequent Supabase CLI operations.
    if env_vars.get('supabase', {}).get('SUPABASE_URL'):
            os.environ['SUPABASE_URL'] = env_vars['supabase']['SUPABASE_URL'] # Set for Supabase CLI
    else:
        print_error("Supabase URL is missing. This is critical for the setup to continue. Please ensure it's provided.")
        sys.exit(1) # Exit if critical information is missing.
    save_env_data(env_vars) # Save the collected/confirmed data.
    current_step += 1

    # Step 3: Collect Agent Sandbox information (Daytona or Local Docker)
    print_step(current_step, total_steps, "Configuring Agent Execution Sandbox")
    daytona_data = env_vars.get('daytona', {})
    reuse_sandbox_config = False
    # Determine if there's a reusable configuration for Daytona or Local Docker.
    if daytona_data.get('SETUP_TYPE') == 'daytona' and daytona_data.get('DAYTONA_API_KEY'):
        reuse_sandbox_config = prompt_to_reuse_config("Daytona Sandbox", daytona_data, specific_check_key='DAYTONA_API_KEY')
    elif daytona_data.get('SETUP_TYPE') == 'local_docker':
        reuse_sandbox_config = prompt_to_reuse_config("Local Docker Sandbox", daytona_data, specific_check_key='SETUP_TYPE')

    if not reuse_sandbox_config:
        env_vars['daytona'] = collect_daytona_info() # Collect sandbox info if not reused.

    save_env_data(env_vars)
    current_step += 1

    # Step 4: Collect LLM (Large Language Model) API keys
    print_step(current_step, total_steps, "Collecting LLM API Keys")
    if not prompt_to_reuse_config("LLM API", env_vars.get('llm'), specific_check_key='MODEL_TO_USE'):
        env_vars['llm'] = collect_llm_api_keys()
    save_env_data(env_vars)
    current_step += 1

    # Step 5: Collect Search and Web Scraping API keys (Tavily, Firecrawl)
    print_step(current_step, total_steps, "Collecting Search & Web Scraping API Keys")
    if not prompt_to_reuse_config("Search/WebScraping API", env_vars.get('search'), specific_check_key='TAVILY_API_KEY'):
        env_vars['search'] = collect_search_api_keys()
    save_env_data(env_vars)
    current_step += 1

    # Step 6: Collect RapidAPI key (optional, for additional API services)
    print_step(current_step, total_steps, "Collecting RapidAPI Key (Optional)")
    if not prompt_to_reuse_config("RapidAPI", env_vars.get('rapidapi'), specific_check_key='RAPID_API_KEY'):
        env_vars['rapidapi'] = collect_rapidapi_keys()
    save_env_data(env_vars)
    current_step += 1

    # Step 7: Setup Supabase (database migrations)
    print_step(current_step, total_steps, "Setting up Supabase Database (Migrations)")
    # This step involves running Supabase CLI commands to prepare the database schema.
    setup_supabase()
    current_step += 1

    # Step 8: Install dependencies, configure .env files, and start Suna services
    print_step(current_step, total_steps, "Installing Dependencies & Finalizing Setup")
    install_dependencies() # Installs frontend (npm) and backend (poetry) dependencies.

    print_info("Configuring Suna environment files (.env files)...")
    # Initial configuration assuming Docker Compose will be used for Suna services.
    # This sets Redis/RabbitMQ hostnames to service names (e.g., 'redis', 'rabbitmq').
    configure_backend_env(env_vars, True)
    configure_frontend_env(env_vars, True)

    print_step(current_step, total_steps, "Starting Suna Services") # Note: current_step is 8 here.
    # start_suna() asks the user if they want to use Docker Compose or start manually.
    # It returns True if Docker Compose is chosen for Suna services, False for manual.
    use_docker_for_suna_services = start_suna()

    # If the user chose manual startup for Suna services (backend, frontend, worker),
    # the .env files need to be reconfigured for localhost Redis/RabbitMQ.
    if not use_docker_for_suna_services:
        print_info("Re-configuring environment files for manual startup (Redis/RabbitMQ on localhost)...")
        configure_backend_env(env_vars, False) # Pass False to set Redis/RabbitMQ to localhost
        configure_frontend_env(env_vars, False) # Though this currently doesn't change for frontend

    final_instructions(use_docker_for_suna_services, env_vars)

    # The .setup_env.json file (ENV_DATA_FILE) is intentionally kept after setup completion.
    # This allows users to re-run the setup script and reuse their previously entered
    # configurations if needed (e.g., after pulling updates that require new .env settings,
    # or if they want to change a specific part of the configuration without re-entering everything).
    # To force a completely fresh setup, the user can manually delete .setup_env.json.
    #
    # Previously, this file might have been deleted upon successful setup.
    # Example of old code that would delete it:
    # if os.path.exists(ENV_DATA_FILE):
    #     os.remove(ENV_DATA_FILE)
    print_info(f"Setup data is saved in {Colors.YELLOW}{ENV_DATA_FILE}{Colors.ENDC} for future runs.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully, allowing user to resume later.
        print(f"\n\n{Colors.YELLOW}Setup interrupted by user (Ctrl+C).{Colors.ENDC}")
        print("You can resume setup anytime by running this script again.")
        sys.exit(1)
