"""FileSystemAdapter - Adapter for loading/saving configuration files.

Provides file-based configuration management with:
- YAML loading and saving
- JSON loading and saving
- Schema validation (optional)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"Configuration error in '{path}': {message}")


class FileSystemAdapter:
    """Adapter for file-based configuration management.

    Supports YAML and JSON configuration files with optional integrity checking.
    """

    def __init__(self, base_path: str | Path | None = None) -> None:
        """Initialize FileSystemAdapter.

        Args:
            base_path: Base directory for configuration files (defaults to cwd)
        """
        self._base_path = Path(base_path) if base_path else Path.cwd()

    def _resolve_path(self, path: str | Path) -> Path:
        """Resolve path relative to base path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self._base_path / p

    def load_yaml(self, path: str | Path) -> dict[str, Any]:
        """Load configuration from YAML file.

        Args:
            path: Path to YAML file (absolute or relative to base_path)

        Returns:
            Dictionary with configuration

        Raises:
            FileNotFoundError: If file doesn't exist
            ConfigurationError: If YAML is invalid
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {full_path}")

        try:
            with open(full_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                return {}

            if not isinstance(data, dict):
                raise ConfigurationError(str(path), "Root element must be a dictionary")

            return data

        except yaml.YAMLError as e:
            raise ConfigurationError(str(path), f"Invalid YAML: {e}") from e

    def save_yaml(
        self,
        path: str | Path,
        data: dict[str, Any],
        *,
        create_dirs: bool = True,
    ) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to YAML file
            data: Configuration dictionary
            create_dirs: Create parent directories if needed

        Raises:
            ConfigurationError: If data is not a dictionary
        """
        if not isinstance(data, dict):
            raise ConfigurationError(str(path), "Data must be a dictionary")

        full_path = self._resolve_path(path)

        if create_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def load_json(self, path: str | Path) -> dict[str, Any]:
        """Load configuration from JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Dictionary with configuration

        Raises:
            FileNotFoundError: If file doesn't exist
            ConfigurationError: If JSON is invalid
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {full_path}")

        try:
            with open(full_path, encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ConfigurationError(str(path), "Root element must be a dictionary")

            return data

        except json.JSONDecodeError as e:
            raise ConfigurationError(str(path), f"Invalid JSON: {e}") from e

    def save_json(
        self,
        path: str | Path,
        data: dict[str, Any],
        *,
        create_dirs: bool = True,
        indent: int = 2,
    ) -> None:
        """Save configuration to JSON file.

        Args:
            path: Path to JSON file
            data: Configuration dictionary
            create_dirs: Create parent directories if needed
            indent: JSON indentation level
        """
        if not isinstance(data, dict):
            raise ConfigurationError(str(path), "Data must be a dictionary")

        full_path = self._resolve_path(path)

        if create_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, default=str)

    def exists(self, path: str | Path) -> bool:
        """Check if file exists.

        Args:
            path: Path to check

        Returns:
            True if file exists
        """
        return self._resolve_path(path).exists()

    def compute_hash(self, path: str | Path) -> str:
        """Compute SHA-256 hash of file for integrity checking.

        Args:
            path: Path to file

        Returns:
            Hex-encoded SHA-256 hash

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")

        sha256 = hashlib.sha256()
        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def validate_hash(self, path: str | Path, expected_hash: str) -> bool:
        """Validate file integrity against expected hash.

        Args:
            path: Path to file
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches
        """
        actual_hash = self.compute_hash(path)
        return actual_hash == expected_hash.lower()

    def list_files(
        self,
        directory: str | Path,
        pattern: str = "*",
    ) -> list[Path]:
        """List files in directory matching pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern (default: all files)

        Returns:
            List of file paths
        """
        dir_path = self._resolve_path(directory)

        if not dir_path.exists():
            return []

        return sorted(dir_path.glob(pattern))
