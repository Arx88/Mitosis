import pytest
import asyncio
import os
from unittest.mock import patch, AsyncMock, MagicMock

# Define mandatory environment variables for Configuration initialization FIRST
MANDATORY_ENV_VARS = {
    "ENV_MODE": "local",
    "STRIPE_FREE_TIER_ID_PROD": "dummy_prod_free",
    "STRIPE_TIER_2_20_ID_PROD": "dummy_prod_t2",
    "STRIPE_TIER_6_50_ID_PROD": "dummy_prod_t6",
    "STRIPE_TIER_12_100_ID_PROD": "dummy_prod_t12",
    "STRIPE_TIER_25_200_ID_PROD": "dummy_prod_t25",
    "STRIPE_TIER_50_400_ID_PROD": "dummy_prod_t50",
    "STRIPE_TIER_125_800_ID_PROD": "dummy_prod_t125",
    "STRIPE_TIER_200_1000_ID_PROD": "dummy_prod_t200",
    "STRIPE_FREE_TIER_ID_STAGING": "dummy_staging_free",
    "STRIPE_TIER_2_20_ID_STAGING": "dummy_staging_t2",
    "STRIPE_TIER_6_50_ID_STAGING": "dummy_staging_t6",
    "STRIPE_TIER_12_100_ID_STAGING": "dummy_staging_t12",
    "STRIPE_TIER_25_200_ID_STAGING": "dummy_staging_t25",
    "STRIPE_TIER_50_400_ID_STAGING": "dummy_staging_t50",
    "STRIPE_TIER_125_800_ID_STAGING": "dummy_staging_t125",
    "STRIPE_TIER_200_1000_ID_STAGING": "dummy_staging_t200",
    "ANTHROPIC_API_KEY": "dummy_anthropic_key",
    "SUPABASE_URL": "http://dummy.supabase.co",
    "SUPABASE_ANON_KEY": "dummy_anon_key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy_service_key",
    "REDIS_HOST": "dummy_redis_host",
    "REDIS_PORT": "6379",
    "REDIS_PASSWORD": "dummy_redis_pass",
    "REDIS_SSL": "True",
    "TAVILY_API_KEY": "dummy_tavily_key",
    "RAPID_API_KEY": "dummy_rapidapi_key",
    "FIRECRAWL_API_KEY": "dummy_firecrawl_key",
    "STRIPE_PRODUCT_ID_PROD": "dummy_stripe_prod_id_prod",
    "STRIPE_PRODUCT_ID_STAGING": "dummy_stripe_prod_id_staging",
    "LANGFUSE_HOST": "http://dummy.langfuse.host",
    "OLLAMA_API_BASE": "http://localhost:11434",
    "OPENAI_API_KEY": "dummy_openai_key",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_test_dummy",
}

env_patcher = patch.dict(os.environ, MANDATORY_ENV_VARS, clear=True)
env_patcher.start()

from backend.services.billing import get_available_models
from backend.utils.config import EnvMode

MOCK_MODEL_NAME_ALIASES = {
    "static_model_1": "openai/gpt-3.5-turbo",
    "static_model_2": "anthropic/claude-2",
}
MOCK_STRIPE_FREE_TIER_ID = "price_free_tier_id_test"

@pytest.fixture(scope="session", autouse=True)
def stop_env_patcher(request):
    request.addfinalizer(env_patcher.stop)

@pytest.mark.asyncio
@patch('backend.services.billing.config', new_callable=MagicMock)
async def test_get_available_models_ollama_success_simplified_debug(
    mock_b_config_arg
):
    assert mock_b_config_arg is not None
    mock_b_config_arg.OLLAMA_API_BASE = "http://fake-ollama:11434"
    mock_b_config_arg.ENV_MODE = EnvMode.PRODUCTION
    mock_b_config_arg.STRIPE_FREE_TIER_ID = MOCK_STRIPE_FREE_TIER_ID
    print(f"Mock config object: {mock_b_config_arg}")
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_get_available_models_ollama_success_context_managers():
    with patch('backend.services.billing.get_current_user_id_from_jwt', return_value="test_user_id"), \
         patch('backend.services.billing.DBConnection') as mock_db_connection_arg, \
         patch('backend.services.billing.config', new_callable=MagicMock) as mock_b_config_arg, \
         patch('aiohttp.ClientSession') as mock_aiohttp_session_class, \
         patch('backend.services.billing.MODEL_NAME_ALIASES', MOCK_MODEL_NAME_ALIASES), \
         patch('backend.services.billing.MODEL_ACCESS_TIERS', {"free": ["openai/gpt-3.5-turbo"]}), \
         patch('backend.services.billing.SUBSCRIPTION_TIERS', {MOCK_STRIPE_FREE_TIER_ID: {'name': 'free', 'minutes': 0}}):

        mock_b_config_arg.OLLAMA_API_BASE = "http://fake-ollama:11434"
        mock_b_config_arg.ENV_MODE = EnvMode.PRODUCTION
        mock_b_config_arg.STRIPE_FREE_TIER_ID = MOCK_STRIPE_FREE_TIER_ID

        mock_db_conn_instance = mock_db_connection_arg.return_value
        mock_supabase_client = AsyncMock()
        async def actual_client_coroutine(): return mock_supabase_client
        mock_db_conn_instance.client = actual_client_coroutine()

        # Configure aiohttp.ClientSession mock
        # mock_aiohttp_session_class is the mock for the ClientSession class
        # mock_aiohttp_session_class.return_value is the mock for the ClientSession instance
        mock_session_instance = mock_aiohttp_session_class.return_value
        # The ClientSession instance itself is an async context manager
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance) # __aenter__ returns the session instance
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        mock_ollama_response = AsyncMock()
        mock_ollama_response.status = 200
        mock_ollama_response.json = AsyncMock(return_value={"models": [{"name": "test-ollama-model:latest"}]})

        # The object returned by session.get() is also an async context manager
        mock_client_response_ctx_manager = MagicMock()
        mock_client_response_ctx_manager.__aenter__ = AsyncMock(return_value=mock_ollama_response)
        mock_client_response_ctx_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_instance.get.return_value = mock_client_response_ctx_manager


        with patch('backend.services.billing.get_allowed_models_for_user', new_callable=AsyncMock) as mock_get_allowed_models, \
             patch('backend.services.billing.get_user_subscription', new_callable=AsyncMock) as mock_get_subscription:

            mock_get_allowed_models.return_value = ["openai/gpt-3.5-turbo"]
            mock_get_subscription.return_value = {
                'price_id': MOCK_STRIPE_FREE_TIER_ID,
                'plan_name': 'free',
                'items': {'data': [{'price': {'id': MOCK_STRIPE_FREE_TIER_ID}}]}
            }

            result = await get_available_models(current_user_id="test_user_id")

            mock_session_instance.get.assert_called_once_with("http://fake-ollama:11434/api/tags", timeout=5)

            found_ollama_model = any(
                model["id"] == "ollama/test-ollama-model:latest" and
                model["display_name"] == "Ollama:test-ollama-model:latest" and
                model["short_name"] == "test-ollama-model:latest" and
                model["requires_subscription"] is False and
                model["is_available"] is True
                for model in result["models"]
            )
            assert found_ollama_model, "Ollama model not found or incorrect in results"

            found_static_model = any(m["id"] == "openai/gpt-3.5-turbo" for m in result["models"])
            assert found_static_model, "Static allowed model not found"

@pytest.mark.asyncio
async def test_get_available_models_ollama_failure_network_error_context_managers():
    with patch('backend.services.billing.get_current_user_id_from_jwt', return_value="test_user_id"), \
         patch('backend.services.billing.DBConnection') as mock_db_connection_arg, \
         patch('backend.services.billing.config', new_callable=MagicMock) as mock_b_config_arg, \
         patch('aiohttp.ClientSession') as mock_aiohttp_session_class, \
         patch('backend.services.billing.logger.warning') as mock_logger_warning_arg, \
         patch('backend.services.billing.MODEL_NAME_ALIASES', MOCK_MODEL_NAME_ALIASES), \
         patch('backend.services.billing.MODEL_ACCESS_TIERS', {"free": ["openai/gpt-3.5-turbo"]}), \
         patch('backend.services.billing.SUBSCRIPTION_TIERS', {MOCK_STRIPE_FREE_TIER_ID: {'name': 'free', 'minutes': 0}}):

        mock_b_config_arg.OLLAMA_API_BASE = "http://fake-ollama:11434"
        mock_b_config_arg.ENV_MODE = EnvMode.PRODUCTION
        mock_b_config_arg.STRIPE_FREE_TIER_ID = MOCK_STRIPE_FREE_TIER_ID

        mock_db_conn_instance = mock_db_connection_arg.return_value
        mock_supabase_client = AsyncMock()
        async def actual_client_coroutine(): return mock_supabase_client
        mock_db_conn_instance.client = actual_client_coroutine()

        mock_session_instance = mock_aiohttp_session_class.return_value
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        import aiohttp
        mock_session_instance.get.side_effect = aiohttp.ClientError("Network connection failed")

        with patch('backend.services.billing.get_allowed_models_for_user', new_callable=AsyncMock) as mock_get_allowed_models, \
             patch('backend.services.billing.get_user_subscription', new_callable=AsyncMock) as mock_get_subscription:

            mock_get_allowed_models.return_value = ["openai/gpt-3.5-turbo"]
            mock_get_subscription.return_value = {
                'price_id': MOCK_STRIPE_FREE_TIER_ID,
                'plan_name': 'free',
                'items': {'data': [{'price': {'id': MOCK_STRIPE_FREE_TIER_ID}}]}
            }

            result = await get_available_models(current_user_id="test_user_id")

            mock_session_instance.get.assert_called_once_with("http://fake-ollama:11434/api/tags", timeout=5)

            ollama_model_present = any(model["id"].startswith("ollama/") for model in result["models"])
            assert not ollama_model_present
            mock_logger_warning_arg.assert_called_once()
            args, _ = mock_logger_warning_arg.call_args
            assert "AIOHTTP client error" in args[0] or "Network connection failed" in args[0]

            found_static_model = any(m["id"] == "openai/gpt-3.5-turbo" for m in result["models"])
            assert found_static_model

@pytest.mark.asyncio
async def test_get_available_models_ollama_failure_status_500_context_managers():
    with patch('backend.services.billing.get_current_user_id_from_jwt', return_value="test_user_id"), \
         patch('backend.services.billing.DBConnection') as mock_db_connection_arg, \
         patch('backend.services.billing.config', new_callable=MagicMock) as mock_b_config_arg, \
         patch('aiohttp.ClientSession') as mock_aiohttp_session_class, \
         patch('backend.services.billing.logger.warning') as mock_logger_warning_arg, \
         patch('backend.services.billing.MODEL_NAME_ALIASES', MOCK_MODEL_NAME_ALIASES), \
         patch('backend.services.billing.MODEL_ACCESS_TIERS', {"free": ["openai/gpt-3.5-turbo"]}), \
         patch('backend.services.billing.SUBSCRIPTION_TIERS', {MOCK_STRIPE_FREE_TIER_ID: {'name': 'free', 'minutes': 0}}):

        mock_b_config_arg.OLLAMA_API_BASE = "http://fake-ollama:11434"
        mock_b_config_arg.ENV_MODE = EnvMode.PRODUCTION
        mock_b_config_arg.STRIPE_FREE_TIER_ID = MOCK_STRIPE_FREE_TIER_ID

        mock_db_conn_instance = mock_db_connection_arg.return_value
        mock_supabase_client = AsyncMock()
        async def actual_client_coroutine(): return mock_supabase_client
        mock_db_conn_instance.client = actual_client_coroutine()

        mock_session_instance = mock_aiohttp_session_class.return_value
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        mock_ollama_response = AsyncMock()
        mock_ollama_response.status = 500
        mock_ollama_response.text = AsyncMock(return_value="Internal Server Error")

        mock_client_response_ctx_manager = MagicMock()
        mock_client_response_ctx_manager.__aenter__ = AsyncMock(return_value=mock_ollama_response)
        mock_client_response_ctx_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session_instance.get.return_value = mock_client_response_ctx_manager

        with patch('backend.services.billing.get_allowed_models_for_user', new_callable=AsyncMock) as mock_get_allowed_models, \
             patch('backend.services.billing.get_user_subscription', new_callable=AsyncMock) as mock_get_subscription:

            mock_get_allowed_models.return_value = ["openai/gpt-3.5-turbo"]
            mock_get_subscription.return_value = {
                'price_id': MOCK_STRIPE_FREE_TIER_ID,
                'plan_name': 'free',
                'items': {'data': [{'price': {'id': MOCK_STRIPE_FREE_TIER_ID}}]}
            }

            result = await get_available_models(current_user_id="test_user_id")

            mock_session_instance.get.assert_called_once_with("http://fake-ollama:11434/api/tags", timeout=5)

            ollama_model_present = any(model["id"].startswith("ollama/") for model in result["models"])
            assert not ollama_model_present

            mock_logger_warning_arg.assert_called_once()
            args, _ = mock_logger_warning_arg.call_args
            assert "Could not fetch models from Ollama server" in args[0]
            assert "Status: 500" in args[0]

            found_static_model = any(m["id"] == "openai/gpt-3.5-turbo" for m in result["models"])
            assert found_static_model

import aiohttp
