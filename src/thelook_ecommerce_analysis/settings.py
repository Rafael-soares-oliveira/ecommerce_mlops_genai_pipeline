from dotenv import load_dotenv
from kedro.config import OmegaConfigLoader

from thelook_ecommerce_analysis.hooks import CreateIndexesHook, ResourceMonitoringHook

load_dotenv()

HOOKS = (ResourceMonitoringHook(), CreateIndexesHook())

CONFIG_LOADER_CLASS = OmegaConfigLoader

CONFIG_LOADER_ARGS = {
    "base_env": "base",
    "default_run_env": "local",
    "config_patterns": {
        "parameters": [
            "parameters*",
            "parameters*/**",
            "globals.yml",
        ]
    },
}
