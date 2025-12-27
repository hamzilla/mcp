"""
Main entry point for Bitbucket MCP Server.
"""

import asyncio
import sys

from config import Settings
from server import BitbucketPipelineServer


async def main():
    """Run the Bitbucket MCP server."""
    try:
        # Load settings from environment
        settings = Settings()

        # Create and run server
        server = BitbucketPipelineServer(settings)

        try:
            await server.run()
        finally:
            await server.cleanup()

    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
