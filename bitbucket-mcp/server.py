"""
Bitbucket MCP Server - Pipeline Operations

This MCP server provides tools for interacting with Bitbucket pipelines,
including listing pipelines, getting pipeline details, analyzing failures,
and retrieving logs.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Optional
from collections import Counter

import httpx
from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from pydantic import AnyUrl

from config import Settings


class BitbucketPipelineServer:
    """MCP Server for Bitbucket Pipeline operations."""

    def __init__(self, settings: Settings):
        """Initialize the Bitbucket Pipeline server."""
        self.settings = settings
        self.server = Server("bitbucket-pipeline-server")
        self.client = httpx.AsyncClient(
            base_url=settings.bitbucket_api_url,
            headers=self._get_auth_headers(),
            timeout=30.0,
        )

        # Register handlers
        self._register_handlers()

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for Bitbucket API."""
        headers = {"Accept": "application/json"}

        if self.settings.bitbucket_token:
            headers["Authorization"] = f"Bearer {self.settings.bitbucket_token}"
        elif self.settings.bitbucket_username and self.settings.bitbucket_password:
            import base64
            credentials = f"{self.settings.bitbucket_username}:{self.settings.bitbucket_password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        return headers

    def _register_handlers(self):
        """Register MCP handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="list_pipelines",
                    description=f"List pipelines for a repository. Returns recent pipelines with their status, duration, and basic info.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "status": {
                                "type": "string",
                                "description": "Filter by status: SUCCESSFUL, FAILED, ERROR, STOPPED, PENDING, or IN_PROGRESS",
                                "enum": ["SUCCESSFUL", "FAILED", "ERROR", "STOPPED", "PENDING", "IN_PROGRESS"],
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of pipelines to return (default: 50, max: 100)",
                                "default": 50,
                            },
                        },
                        "required": [] if self.settings.bitbucket_repo_slug else ["repo_slug"],
                    },
                ),
                Tool(
                    name="get_pipeline_details",
                    description=f"Get detailed information about a specific pipeline including all steps and their status.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "pipeline_uuid": {
                                "type": "string",
                                "description": "Pipeline UUID (with or without curly braces)",
                            },
                        },
                        "required": ["pipeline_uuid"] if self.settings.bitbucket_repo_slug else ["repo_slug", "pipeline_uuid"],
                    },
                ),
                Tool(
                    name="get_failed_pipelines",
                    description=f"Get all failed pipelines for a repository with details about what failed.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of pipelines to check (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": [] if self.settings.bitbucket_repo_slug else ["repo_slug"],
                    },
                ),
                Tool(
                    name="get_step_logs",
                    description=f"Get logs for a specific pipeline step.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "pipeline_uuid": {
                                "type": "string",
                                "description": "Pipeline UUID",
                            },
                            "step_uuid": {
                                "type": "string",
                                "description": "Step UUID",
                            },
                        },
                        "required": ["pipeline_uuid", "step_uuid"] if self.settings.bitbucket_repo_slug else ["repo_slug", "pipeline_uuid", "step_uuid"],
                    },
                ),
                Tool(
                    name="analyze_step_failures",
                    description=f"Analyze which pipeline steps fail most frequently across recent pipeline runs.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Number of recent pipelines to analyze (default: 100)",
                                "default": 100,
                            },
                        },
                        "required": [] if self.settings.bitbucket_repo_slug else ["repo_slug"],
                    },
                ),
                Tool(
                    name="get_latest_failure_logs",
                    description=f"Get logs from the most recent failed pipeline, automatically identifying the failed step.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                        },
                        "required": [] if self.settings.bitbucket_repo_slug else ["repo_slug"],
                    },
                ),
                Tool(
                    name="run_pipeline",
                    description=f"Trigger a new pipeline execution for a repository.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "ref_type": {
                                "type": "string",
                                "description": "Reference type: branch, tag, bookmark, or named_branch",
                                "enum": ["branch", "tag", "bookmark", "named_branch"],
                            },
                            "ref_name": {
                                "type": "string",
                                "description": "Name of the branch, tag, or bookmark",
                            },
                            "variables": {
                                "type": "array",
                                "description": "Optional pipeline variables as array of {key, value, secured} objects",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "key": {"type": "string"},
                                        "value": {"type": "string"},
                                        "secured": {"type": "boolean"},
                                    },
                                    "required": ["key", "value"],
                                },
                            },
                        },
                        "required": ["ref_type", "ref_name"] if self.settings.bitbucket_repo_slug else ["repo_slug", "ref_type", "ref_name"],
                    },
                ),
                Tool(
                    name="stop_pipeline",
                    description=f"Stop a currently running pipeline.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "pipeline_uuid": {
                                "type": "string",
                                "description": "Pipeline UUID to stop",
                            },
                        },
                        "required": ["pipeline_uuid"] if self.settings.bitbucket_repo_slug else ["repo_slug", "pipeline_uuid"],
                    },
                ),
                Tool(
                    name="get_pipeline_steps",
                    description=f"Get all steps for a specific pipeline.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "pipeline_uuid": {
                                "type": "string",
                                "description": "Pipeline UUID",
                            },
                        },
                        "required": ["pipeline_uuid"] if self.settings.bitbucket_repo_slug else ["repo_slug", "pipeline_uuid"],
                    },
                ),
                Tool(
                    name="get_pipeline_step",
                    description=f"Get detailed information about a specific pipeline step.{' Default repo: ' + self.settings.bitbucket_repo_slug if self.settings.bitbucket_repo_slug else ''}",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workspace": {
                                "type": "string",
                                "description": f"Bitbucket workspace name (defaults to {self.settings.bitbucket_workspace})",
                            },
                            "repo_slug": {
                                "type": "string",
                                "description": f"Repository slug/name{' (defaults to ' + self.settings.bitbucket_repo_slug + ')' if self.settings.bitbucket_repo_slug else ''}",
                            },
                            "pipeline_uuid": {
                                "type": "string",
                                "description": "Pipeline UUID",
                            },
                            "step_uuid": {
                                "type": "string",
                                "description": "Step UUID",
                            },
                        },
                        "required": ["pipeline_uuid", "step_uuid"] if self.settings.bitbucket_repo_slug else ["repo_slug", "pipeline_uuid", "step_uuid"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "list_pipelines":
                    result = await self.list_pipelines(**arguments)
                elif name == "get_pipeline_details":
                    result = await self.get_pipeline_details(**arguments)
                elif name == "get_failed_pipelines":
                    result = await self.get_failed_pipelines(**arguments)
                elif name == "get_step_logs":
                    result = await self.get_step_logs(**arguments)
                elif name == "analyze_step_failures":
                    result = await self.analyze_step_failures(**arguments)
                elif name == "get_latest_failure_logs":
                    result = await self.get_latest_failure_logs(**arguments)
                elif name == "run_pipeline":
                    result = await self.run_pipeline(**arguments)
                elif name == "stop_pipeline":
                    result = await self.stop_pipeline(**arguments)
                elif name == "get_pipeline_steps":
                    result = await self.get_pipeline_steps(**arguments)
                elif name == "get_pipeline_step":
                    result = await self.get_pipeline_step(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    def _normalize_uuid(self, uuid: str) -> str:
        """Normalize UUID format (add curly braces if missing)."""
        uuid = uuid.strip()
        if not uuid.startswith("{"):
            uuid = "{" + uuid
        if not uuid.endswith("}"):
            uuid = uuid + "}"
        return uuid

    def _get_workspace(self, workspace: Optional[str] = None) -> str:
        """Get workspace, using default if not provided."""
        return workspace or self.settings.bitbucket_workspace

    def _get_repo_slug(self, repo_slug: Optional[str] = None) -> str:
        """Get repo_slug, using default if not provided."""
        result = repo_slug or self.settings.bitbucket_repo_slug
        if not result:
            raise ValueError(
                "repo_slug is required: provide it as a parameter or set BITBUCKET_REPO_SLUG in .env"
            )
        return result

    async def list_pipelines(
        self,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List pipelines for a repository."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)
        url = f"/repositories/{ws}/{rs}/pipelines/"

        params = {"pagelen": min(limit, 100), "sort": "-created_on"}
        if status:
            params["target.ref_name"] = status

        response = await self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        pipelines = []
        for pipeline in data.get("values", [])[:limit]:
            state = pipeline.get("state", {})

            pipelines.append({
                "uuid": pipeline.get("uuid"),
                "build_number": pipeline.get("build_number"),
                "status": state.get("name"),
                "result": state.get("result", {}).get("name") if state.get("result") else None,
                "created_on": pipeline.get("created_on"),
                "completed_on": pipeline.get("completed_on"),
                "duration_seconds": pipeline.get("duration_in_seconds"),
                "trigger": pipeline.get("trigger", {}).get("name"),
                "target": {
                    "ref_type": pipeline.get("target", {}).get("ref_type"),
                    "ref_name": pipeline.get("target", {}).get("ref_name"),
                    "commit": pipeline.get("target", {}).get("commit", {}).get("hash", "")[:7],
                },
            })

        return {
            "workspace": ws,
            "repository": rs,
            "total": len(pipelines),
            "pipelines": pipelines,
        }

    async def get_pipeline_details(
        self,
        pipeline_uuid: str,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get detailed information about a specific pipeline."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)
        pipeline_uuid = self._normalize_uuid(pipeline_uuid)

        # Get pipeline info
        url = f"/repositories/{ws}/{rs}/pipelines/{pipeline_uuid}"
        response = await self.client.get(url)
        response.raise_for_status()
        pipeline = response.json()

        # Get pipeline steps
        steps_url = f"/repositories/{ws}/{rs}/pipelines/{pipeline_uuid}/steps/"
        steps_response = await self.client.get(steps_url)
        steps_response.raise_for_status()
        steps_data = steps_response.json()

        steps = []
        for step in steps_data.get("values", []):
            state = step.get("state", {})
            steps.append({
                "uuid": step.get("uuid"),
                "name": step.get("name"),
                "status": state.get("name"),
                "result": state.get("result", {}).get("name") if state.get("result") else None,
                "duration_seconds": step.get("duration_in_seconds"),
                "started_on": step.get("started_on"),
                "completed_on": step.get("completed_on"),
            })

        state = pipeline.get("state", {})
        return {
            "uuid": pipeline.get("uuid"),
            "build_number": pipeline.get("build_number"),
            "status": state.get("name"),
            "result": state.get("result", {}).get("name") if state.get("result") else None,
            "created_on": pipeline.get("created_on"),
            "completed_on": pipeline.get("completed_on"),
            "duration_seconds": pipeline.get("duration_in_seconds"),
            "trigger": pipeline.get("trigger"),
            "target": pipeline.get("target"),
            "steps": steps,
        }

    async def get_failed_pipelines(
        self,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get all failed pipelines for a repository."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)

        # Get all recent pipelines
        all_pipelines = await self.list_pipelines(
            repo_slug=rs,
            workspace=ws,
            limit=limit,
        )

        failed_pipelines = []
        for pipeline in all_pipelines["pipelines"]:
            if pipeline["result"] in ["FAILED", "ERROR"]:
                # Get details including steps
                details = await self.get_pipeline_details(
                    pipeline_uuid=pipeline["uuid"],
                    repo_slug=rs,
                    workspace=ws,
                )

                # Find failed steps
                failed_steps = [
                    step for step in details["steps"]
                    if step.get("result") in ["FAILED", "ERROR"]
                ]

                failed_pipelines.append({
                    "uuid": pipeline["uuid"],
                    "build_number": pipeline["build_number"],
                    "status": pipeline["status"],
                    "result": pipeline["result"],
                    "created_on": pipeline["created_on"],
                    "failed_steps": [
                        {
                            "name": step["name"],
                            "uuid": step["uuid"],
                            "result": step["result"],
                        }
                        for step in failed_steps
                    ],
                })

        return {
            "workspace": ws,
            "repository": rs,
            "total_failed": len(failed_pipelines),
            "failed_pipelines": failed_pipelines,
        }

    async def get_step_logs(
        self,
        pipeline_uuid: str,
        step_uuid: str,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get logs for a specific pipeline step."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)
        pipeline_uuid = self._normalize_uuid(pipeline_uuid)
        step_uuid = self._normalize_uuid(step_uuid)

        url = f"/repositories/{ws}/{rs}/pipelines/{pipeline_uuid}/steps/{step_uuid}/log"

        # The logs endpoint redirects to S3, so we need to:
        # 1. Follow redirects (follow_redirects=True)
        # 2. Use Accept: */* instead of application/json
        response = await self.client.get(
            url,
            headers={"Accept": "*/*"},
            follow_redirects=True
        )
        response.raise_for_status()

        # Logs are returned as plain text
        logs = response.text

        return {
            "workspace": ws,
            "repository": rs,
            "pipeline_uuid": pipeline_uuid,
            "step_uuid": step_uuid,
            "logs": logs,
        }

    async def analyze_step_failures(
        self,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Analyze which steps fail most frequently."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)

        # Get recent pipelines
        all_pipelines = await self.list_pipelines(
            repo_slug=rs,
            workspace=ws,
            limit=limit,
        )

        step_failures: Counter = Counter()
        total_pipelines = 0
        failed_pipelines = 0

        for pipeline in all_pipelines["pipelines"]:
            total_pipelines += 1

            if pipeline["result"] in ["FAILED", "ERROR"]:
                failed_pipelines += 1

                # Get pipeline details to see which steps failed
                details = await self.get_pipeline_details(
                    pipeline_uuid=pipeline["uuid"],
                    repo_slug=rs,
                    workspace=ws,
                )

                for step in details["steps"]:
                    if step.get("result") in ["FAILED", "ERROR"]:
                        step_failures[step["name"]] += 1

        # Format results
        failure_stats = [
            {"step_name": step_name, "failure_count": count}
            for step_name, count in step_failures.most_common()
        ]

        return {
            "workspace": ws,
            "repository": rs,
            "analyzed_pipelines": total_pipelines,
            "failed_pipelines": failed_pipelines,
            "failure_rate": f"{(failed_pipelines / total_pipelines * 100):.1f}%" if total_pipelines > 0 else "0%",
            "step_failure_stats": failure_stats,
        }

    async def get_latest_failure_logs(
        self,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get logs from the most recent failed pipeline."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)

        # Get recent pipelines
        pipelines = await self.list_pipelines(
            repo_slug=rs,
            workspace=ws,
            limit=50,
        )

        # Find first failed pipeline
        failed_pipeline = None
        for pipeline in pipelines["pipelines"]:
            if pipeline["result"] in ["FAILED", "ERROR"]:
                failed_pipeline = pipeline
                break

        if not failed_pipeline:
            return {
                "workspace": ws,
                "repository": rs,
                "message": "No failed pipelines found in recent history",
            }

        # Get pipeline details
        details = await self.get_pipeline_details(
            pipeline_uuid=failed_pipeline["uuid"],
            repo_slug=rs,
            workspace=ws,
        )

        # Find failed step
        failed_step = None
        for step in details["steps"]:
            if step.get("result") in ["FAILED", "ERROR"]:
                failed_step = step
                break

        if not failed_step:
            return {
                "workspace": ws,
                "repository": rs,
                "pipeline": failed_pipeline,
                "message": "Failed pipeline found but no failed step identified",
            }

        # Get logs for the failed step
        logs = await self.get_step_logs(
            pipeline_uuid=failed_pipeline["uuid"],
            step_uuid=failed_step["uuid"],
            repo_slug=rs,
            workspace=ws,
        )

        return {
            "workspace": ws,
            "repository": rs,
            "pipeline": {
                "uuid": failed_pipeline["uuid"],
                "build_number": failed_pipeline["build_number"],
                "created_on": failed_pipeline["created_on"],
                "result": failed_pipeline["result"],
            },
            "failed_step": {
                "name": failed_step["name"],
                "uuid": failed_step["uuid"],
                "result": failed_step["result"],
                "duration_seconds": failed_step.get("duration_seconds"),
            },
            "logs": logs["logs"],
        }

    async def run_pipeline(
        self,
        ref_type: str,
        ref_name: str,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
        variables: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Trigger a new pipeline execution."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)

        url = f"/repositories/{ws}/{rs}/pipelines/"

        # Build the request body according to Bitbucket API
        body = {
            "target": {
                "ref_type": ref_type,
                "type": "pipeline_ref_target",
                "ref_name": ref_name,
            }
        }

        # Add variables if provided
        if variables:
            body["variables"] = variables

        response = await self.client.post(url, json=body)
        response.raise_for_status()
        pipeline = response.json()

        return {
            "workspace": ws,
            "repository": rs,
            "pipeline": {
                "uuid": pipeline.get("uuid"),
                "build_number": pipeline.get("build_number"),
                "state": pipeline.get("state", {}).get("name"),
                "created_on": pipeline.get("created_on"),
                "target": pipeline.get("target"),
            },
            "message": f"Pipeline triggered successfully for {ref_type} {ref_name}",
        }

    async def stop_pipeline(
        self,
        pipeline_uuid: str,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Stop a running pipeline."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)
        pipeline_uuid = self._normalize_uuid(pipeline_uuid)

        url = f"/repositories/{ws}/{rs}/pipelines/{pipeline_uuid}/stopPipeline"

        # Empty POST request to stop the pipeline
        response = await self.client.post(url, json={})
        response.raise_for_status()

        return {
            "workspace": ws,
            "repository": rs,
            "pipeline_uuid": pipeline_uuid,
            "message": "Pipeline stop signal sent successfully",
        }

    async def get_pipeline_steps(
        self,
        pipeline_uuid: str,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get all steps for a specific pipeline."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)
        pipeline_uuid = self._normalize_uuid(pipeline_uuid)

        url = f"/repositories/{ws}/{rs}/pipelines/{pipeline_uuid}/steps/"

        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()

        steps = []
        for step in data.get("values", []):
            state = step.get("state", {})
            steps.append({
                "uuid": step.get("uuid"),
                "name": step.get("name"),
                "state": state.get("name"),
                "result": state.get("result", {}).get("name") if state.get("result") else None,
                "started_on": step.get("started_on"),
                "completed_on": step.get("completed_on"),
                "duration_seconds": step.get("duration_in_seconds"),
            })

        return {
            "workspace": ws,
            "repository": rs,
            "pipeline_uuid": pipeline_uuid,
            "total_steps": len(steps),
            "steps": steps,
        }

    async def get_pipeline_step(
        self,
        pipeline_uuid: str,
        step_uuid: str,
        repo_slug: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get detailed information about a specific pipeline step."""
        ws = self._get_workspace(workspace)
        rs = self._get_repo_slug(repo_slug)
        pipeline_uuid = self._normalize_uuid(pipeline_uuid)
        step_uuid = self._normalize_uuid(step_uuid)

        url = f"/repositories/{ws}/{rs}/pipelines/{pipeline_uuid}/steps/{step_uuid}"

        response = await self.client.get(url)
        response.raise_for_status()
        step = response.json()

        state = step.get("state", {})
        return {
            "workspace": ws,
            "repository": rs,
            "pipeline_uuid": pipeline_uuid,
            "step": {
                "uuid": step.get("uuid"),
                "name": step.get("name"),
                "state": state.get("name"),
                "result": state.get("result", {}).get("name") if state.get("result") else None,
                "started_on": step.get("started_on"),
                "completed_on": step.get("completed_on"),
                "duration_seconds": step.get("duration_in_seconds"),
                "setup_commands": step.get("setup_commands"),
                "script_commands": step.get("script_commands"),
            },
        }

    async def run(self):
        """Run the MCP server."""
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )

    async def cleanup(self):
        """Clean up resources."""
        await self.client.aclose()
