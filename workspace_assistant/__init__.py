"""
Workspace Assistant Package
"""

import sys
from pathlib import Path

# Ensure workspace_assistant directory is in sys.path for direct submodule imports
pkg_dir = str(Path(__file__).parent.resolve())
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from .agent import create_agent, create_agent_with_tool_search, root_agent

__all__ = ["create_agent", "create_agent_with_tool_search", "root_agent"]
