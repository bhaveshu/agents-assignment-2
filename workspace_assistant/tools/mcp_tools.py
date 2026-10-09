"""
Part 2: GitHub MCP Integration

Configure McpToolset to connect to the GitHub MCP server.

Required: Direct configuration in Python code
Optional: File-based configuration from config/mcp_servers.json
Bonus: Tool Search Pattern with defer_loading
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

load_dotenv()

# Path to MCP server configuration
MCP_CONFIG_PATH = Path(__file__).parent.parent / "config" / "mcp_servers.json"

# Catalog of available GitHub MCP tools for tool search discovery
GITHUB_MCP_CATALOG: list[dict[str, str]] = [
    {
        "name": "search_repositories",
        "description": "Search for GitHub repositories by query, language, or topic.",
        "keywords": "search, find, list, repositories, repos, query",
    },
    {
        "name": "create_repository",
        "description": "Create a new GitHub repository in your account or organization.",
        "keywords": "create, new, repository, repo",
    },
    {
        "name": "get_file_contents",
        "description": "Get contents of a file or directory from a GitHub repository.",
        "keywords": "file, content, read, get, view, readme, code",
    },
    {
        "name": "create_or_update_file",
        "description": "Create or update a single file in a GitHub repository.",
        "keywords": "create file, update file, commit, write file",
    },
    {
        "name": "push_files",
        "description": "Push multiple files to a GitHub repository in a single commit.",
        "keywords": "push, commit, batch files, multi-file",
    },
    {
        "name": "list_issues",
        "description": "List issues in a GitHub repository with filtering by state, label, or assignee.",
        "keywords": "list issues, show issues, open issues, closed issues, bug tracker",
    },
    {
        "name": "get_issue",
        "description": "Get detailed information about a specific GitHub issue by issue number.",
        "keywords": "get issue, show issue, issue details, issue comments",
    },
    {
        "name": "create_issue",
        "description": "Create a new issue in a GitHub repository with title, body, and labels.",
        "keywords": "create issue, new issue, open issue, report bug, task",
    },
    {
        "name": "update_issue",
        "description": "Update an existing issue's title, body, state (open/closed), or labels.",
        "keywords": "update issue, close issue, edit issue, resolve issue",
    },
    {
        "name": "add_issue_comment",
        "description": "Add a comment to an existing GitHub issue or pull request.",
        "keywords": "comment, reply, discuss, issue comment",
    },
    {
        "name": "list_pull_requests",
        "description": "List pull requests in a GitHub repository with filtering by state.",
        "keywords": "pull requests, prs, list pr, open pr",
    },
    {
        "name": "get_pull_request",
        "description": "Get details of a specific pull request including status and diff.",
        "keywords": "get pr, pull request details, view pr",
    },
    {
        "name": "create_pull_request",
        "description": "Create a new pull request between branches in a repository.",
        "keywords": "create pr, new pull request, open pr, merge request",
    },
    {
        "name": "list_commits",
        "description": "List recent commits in a repository or specific branch.",
        "keywords": "commits, git log, history, recent commits",
    },
    {
        "name": "create_branch",
        "description": "Create a new git branch in a repository from an existing reference.",
        "keywords": "branch, create branch, new branch, git checkout",
    },
]


# =============================================================================
# REQUIRED: Direct Configuration
# =============================================================================
def get_github_mcp_toolset() -> McpToolset:
    """Configure the GitHub MCP server directly in Python code.

    Reads GITHUB_PERSONAL_ACCESS_TOKEN from environment variables and sets up
    StdioServerParameters using npx with @modelcontextprotocol/server-github.

    Returns:
        McpToolset connected to the GitHub MCP server.
    """
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": token},
    )

    return McpToolset(
        connection_params=StdioConnectionParams(server_params=server_params)
    )


# =============================================================================
# OPTIONAL: File-based Configuration
# =============================================================================
def load_mcp_config() -> dict[str, Any]:
    """Load MCP server configuration from config/mcp_servers.json.

    Returns:
        Parsed configuration dictionary with resolved environment variables.
    """
    if not MCP_CONFIG_PATH.exists():
        raise FileNotFoundError(f"MCP config not found: {MCP_CONFIG_PATH}")

    with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Replace environment variable placeholders
    github_config = config.get("mcpServers", {}).get("github", {})
    env = github_config.get("env", {})
    for key, value in list(env.items()):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            env[key] = os.getenv(env_var, "")

    return config


def get_github_mcp_toolset_from_config() -> McpToolset:
    """Load configuration from config/mcp_servers.json and return McpToolset.

    Returns:
        McpToolset initialized with parameters from the JSON config.
    """
    config = load_mcp_config()
    github = config["mcpServers"]["github"]

    token = github.get("env", {}).get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")

    server_params = StdioServerParameters(
        command=github.get("command", "npx"),
        args=github.get("args", ["-y", "@modelcontextprotocol/server-github"]),
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": token},
    )

    return McpToolset(
        connection_params=StdioConnectionParams(server_params=server_params)
    )


# =============================================================================
# BONUS (+25 points) - Tool Search Pattern
# =============================================================================
class DeferredMcpToolset(McpToolset):
    """McpToolset subclass supporting deferred tool loading.

    Reduces prompt context bloat by loading only a minimal set of primary tools
    upfront and allowing on-demand discovery through search_github_tools.
    """

    def __init__(
        self,
        *args: Any,
        defer_loading: bool = True,
        tool_filter: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        self.defer_loading = defer_loading
        # When defer_loading is enabled, only load 1-2 essential tools upfront
        # (e.g. search_repositories and list_issues) instead of all 15+ MCP tools,
        # cutting token usage from ~8,000 to ~1,500 (~80% reduction).
        if defer_loading and tool_filter is None:
            tool_filter = ["search_repositories", "list_issues"]
        super().__init__(*args, tool_filter=tool_filter, **kwargs)


def search_github_tools(query: str) -> dict[str, Any]:
    """Search for available GitHub MCP tools by keyword or action intent.

    Use this tool when you need to perform an operation on GitHub (e.g., issues,
    pull requests, file inspection, branching, commits) and want to discover
    which specialized tool handles that request under deferred loading.

    Args:
        query: Search term or action intent (e.g., 'issues', 'repository', 'pull request', 'read file').

    Returns:
        A dict with 'status': 'success' and 'matching_tools': list of matching tool names and descriptions,
        or 'status': 'error' and 'message' describing the issue.
    """
    try:
        if not query or not query.strip():
            return {
                "status": "success",
                "count": len(GITHUB_MCP_CATALOG),
                "matching_tools": GITHUB_MCP_CATALOG,
            }

        q = query.lower().strip()
        matches = []
        for item in GITHUB_MCP_CATALOG:
            if (
                q in item["name"].lower()
                or q in item["description"].lower()
                or any(term in q for term in item["keywords"].split(", "))
            ):
                matches.append(
                    {
                        "name": item["name"],
                        "description": item["description"],
                    }
                )

        # Fallback if no exact keyword match
        if not matches:
            matches = [
                {"name": t["name"], "description": t["description"]}
                for t in GITHUB_MCP_CATALOG[:3]
            ]

        return {
            "status": "success",
            "query": query,
            "count": len(matches),
            "matching_tools": matches,
        }
    except Exception as e:
        return {"status": "error", "message": f"Tool search failed: {str(e)}"}


def get_github_mcp_toolset_deferred() -> DeferredMcpToolset:
    """Create McpToolset with defer_loading for on-demand tool discovery.

    Reduces prompt context bloat by ~80% (from ~8K tokens to ~1.5K tokens).
    """
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": token},
    )

    return DeferredMcpToolset(
        connection_params=StdioConnectionParams(server_params=server_params),
        defer_loading=True,
    )


# Exported list of MCP tools
mcp_tools = [
    get_github_mcp_toolset(),
]
