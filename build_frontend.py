#!/usr/bin/env python3
"""
Frontend Build and Serve Script for DLHD Proxy

This script provides Reflex-like functionality for building and serving the frontend
without requiring the full Reflex framework. It uses the existing .web directory
setup created by Reflex.

The script automatically detects and uses available package managers (bun preferred, npm as fallback).

Requirements:
- Python 3.6+
- Either bun OR npm/node.js installed
- Existing .web directory (created by 'reflex init')

Usage:
    python build_frontend.py build    # Build the frontend for production
    python build_frontend.py dev      # Start development server (default port 3001)
    python build_frontend.py serve    # Serve production build (default port 3000)
    python build_frontend.py init     # Check if .web directory exists

Options:
    --host HOST    # Host to bind to (default: localhost)
    --port PORT    # Port to use (default: 3001 for dev, 3000 for serve)

Examples:
    python build_frontend.py build
    python build_frontend.py dev --port 3002
    python build_frontend.py serve --host 0.0.0.0 --port 8080
"""

import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path


class FrontendManager:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.web_dir = self.root_dir / ".web"
        self.build_dir = self.web_dir / "build" / "client"
        self.package_json = self.web_dir / "package.json"

    def check_bun_installed(self):
        """Check if bun is installed and available."""
        try:
            result = subprocess.run(
                ["bun", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"[OK] Bun version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def check_npm_installed(self):
        """Check if npm/node is installed and available."""
        try:
            # Try npm.cmd for Windows
            result = subprocess.run(
                ["npm.cmd", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"[OK] npm version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Try npm without .cmd extension
            try:
                result = subprocess.run(
                    ["npm", "--version"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"[OK] npm version: {result.stdout.strip()}")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False

    def get_package_manager(self):
        """Get the available package manager (bun preferred over npm)."""
        if self.check_bun_installed():
            return "bun"
        elif self.check_npm_installed():
            return "npm.cmd"  # Use npm.cmd on Windows
        else:
            return None

    def check_dependencies(self):
        """Check if frontend dependencies are installed."""
        if not self.package_json.exists():
            print("[ERROR] package.json not found. Run 'reflex init' first or ensure .web directory exists.")
            return False

        # Check if we have a package manager available
        if not (self.check_bun_installed() or self.check_npm_installed()):
            print("[ERROR] Neither bun nor npm/node found. Please install one of them.")
            return False

        node_modules = self.web_dir / "node_modules"
        if not node_modules.exists():
            print("[WARN] node_modules not found. Installing dependencies...")
            return self.install_dependencies()

        print("[OK] Frontend dependencies are installed")
        return True

    def install_dependencies(self):
        """Install frontend dependencies using available package manager."""
        pm = self.get_package_manager()
        if not pm:
            print("[ERROR] No package manager available")
            return False

        print(f"Installing frontend dependencies using {pm}...")
        try:
            subprocess.run(
                [pm, "install"],
                cwd=self.web_dir,
                check=True
            )
            print("[OK] Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to install dependencies: {e}")
            return False

    def build_frontend(self):
        """Build the frontend for production."""
        if not self.check_dependencies():
            return False

        pm = self.get_package_manager()
        if not pm:
            print("[ERROR] No package manager available")
            return False

        print(f"Building frontend using {pm}...")
        try:
            # Clean previous build
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)

            # Build using the export script from package.json
            subprocess.run(
                [pm, "run", "export"],
                cwd=self.web_dir,
                check=True
            )

            if self.build_dir.exists():
                print("[OK] Frontend built successfully")
                print(f"  Build output: {self.build_dir}")
                return True
            else:
                print("[ERROR] Build completed but build directory not found")
                return False

        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Build failed: {e}")
            return False

    def serve_development(self, host="localhost", port=3001):
        """Start the development server."""
        if not self.check_dependencies():
            return False

        pm = self.get_package_manager()
        if not pm:
            print("[ERROR] No package manager available")
            return False

        print(f"Starting development server on http://{host}:{port}")
        print("Press Ctrl+C to stop")

        try:
            # Use the dev script from package.json
            subprocess.run(
                [pm, "run", "dev"],
                cwd=self.web_dir,
                env={**os.environ, "PORT": str(port)},
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Development server failed: {e}")
            return False
        except KeyboardInterrupt:
            print("\n[OK] Development server stopped")
            return True

    def serve_production(self, host="localhost", port=3000):
        """Serve the production build."""
        if not self.build_dir.exists():
            print("[ERROR] Production build not found. Run 'build' first.")
            return False

        pm = self.get_package_manager()
        if not pm:
            print("[ERROR] No package manager available")
            return False

        print(f"Serving production build on http://{host}:{port}")
        print("Press Ctrl+C to stop")

        try:
            # Use the prod script from package.json
            subprocess.run(
                [pm, "run", "prod"],
                cwd=self.web_dir,
                env={**os.environ, "PORT": str(port)},
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Production server failed: {e}")
            return False
        except KeyboardInterrupt:
            print("\n[OK] Production server stopped")
            return True

    def init_frontend(self):
        """Initialize the frontend if .web directory doesn't exist."""
        if self.web_dir.exists():
            print("[OK] .web directory already exists")
            return True

        print("Initializing frontend...")

        # This would normally be done by 'reflex init'
        # For now, we'll assume the .web directory is already set up
        # In a full implementation, we'd need to recreate the Reflex init process

        print("[ERROR] .web directory not found. Please run 'reflex init' first to set up the frontend.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Build and serve DLHD Proxy frontend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_frontend.py build    # Build for production
  python build_frontend.py dev      # Start dev server
  python build_frontend.py serve    # Serve production build
  python build_frontend.py init     # Initialize frontend (if needed)
        """
    )

    parser.add_argument(
        "command",
        choices=["build", "dev", "serve", "init"],
        help="Command to run"
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)"
    )

    parser.add_argument(
        "--port",
        type=int,
        help="Port to use (default: 3001 for dev, 3000 for serve)"
    )

    args = parser.parse_args()

    manager = FrontendManager()

    if args.command == "init":
        success = manager.init_frontend()
    elif args.command == "build":
        success = manager.build_frontend()
    elif args.command == "dev":
        port = args.port or 3001
        success = manager.serve_development(args.host, port)
    elif args.command == "serve":
        port = args.port or 3000
        success = manager.serve_production(args.host, port)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
