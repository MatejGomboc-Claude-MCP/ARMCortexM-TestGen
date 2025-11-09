"""Configuration for ARMCortexM-TestGen"""

import os
from pathlib import Path

# API Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-20250514"

# Temperature settings for different modes
TEMPERATURE = {
    "simple": 0.2,      # Low for consistency
    "supervised": 0.3,  # Slightly higher for diversity
    "consensus": 0.4    # Higher for varied perspectives
}

# Cost per 1M tokens (in USD)
INPUT_TOKEN_COST = 3.0   # $3 per 1M input tokens
OUTPUT_TOKEN_COST = 15.0  # $15 per 1M output tokens

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 300  # 5 minutes

# Validation settings
MAX_COMPILATION_ATTEMPTS = 3

# Output settings
OUTPUT_DIR = Path("output")
LOG_LEVEL = "INFO"