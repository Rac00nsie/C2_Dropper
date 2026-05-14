#!/usr/bin/env python3
"""DigitalOcean C2 Dropper - Main Entry Point."""

import argparse

from c2_dropper import DeploymentOrchestrator, InteractiveConsole
from c2_dropper.api.digitalocean import DigitalOceanAPI


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="DigitalOcean C2 Dropper")
    parser.add_argument(
        "--api-token",
        dest="api_token",
        help="DigitalOcean API token. If omitted, DIGITALOCEAN_TOKEN is used.",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the application."""
    args = parse_args()

    try:
        # Initialize the API client
        api = DigitalOceanAPI(api_token=args.api_token)

        # Create the orchestrator (coordinates all operations)
        orchestrator = DeploymentOrchestrator(api)

        # Start the interactive console
        console = InteractiveConsole(orchestrator)
        console.run()

    except ValueError as e:
        print(f"[-] Error: {e}")
        print("\n[*] Provide the token with --api-token or set DIGITALOCEAN_TOKEN:")
        print("    python main.py --api-token your_token_here")
        print("    set DIGITALOCEAN_TOKEN=your_token_here")
        exit(1)

    except KeyboardInterrupt:
        print("\n\n[*] Interrupted by user. Exiting...")
        exit(0)

    except Exception as e:
        print(f"[-] Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
