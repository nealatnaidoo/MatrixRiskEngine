"""Unit tests for FileSystemAdapter."""

import pytest
from pathlib import Path
import tempfile
import json
import yaml

from src.adapters.filesystem_adapter import FileSystemAdapter, ConfigurationError


class TestFileSystemAdapterYAML:
    """Test YAML loading and saving."""

    def test_load_yaml_valid(self, tmp_path: Path) -> None:
        """Valid YAML should load successfully."""
        yaml_content = """
        name: test
        values:
          - 1
          - 2
          - 3
        nested:
          key: value
        """
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        adapter = FileSystemAdapter(tmp_path)
        result = adapter.load_yaml("config.yaml")

        assert result["name"] == "test"
        assert result["values"] == [1, 2, 3]
        assert result["nested"]["key"] == "value"

    def test_load_yaml_file_not_found(self, tmp_path: Path) -> None:
        """Missing file should raise FileNotFoundError."""
        adapter = FileSystemAdapter(tmp_path)

        with pytest.raises(FileNotFoundError):
            adapter.load_yaml("nonexistent.yaml")

    def test_load_yaml_invalid(self, tmp_path: Path) -> None:
        """Invalid YAML should raise ConfigurationError."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("{ invalid: yaml: content")

        adapter = FileSystemAdapter(tmp_path)

        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            adapter.load_yaml("invalid.yaml")

    def test_load_yaml_non_dict_root(self, tmp_path: Path) -> None:
        """Non-dict root element should raise ConfigurationError."""
        yaml_file = tmp_path / "list.yaml"
        yaml_file.write_text("- item1\n- item2")

        adapter = FileSystemAdapter(tmp_path)

        with pytest.raises(ConfigurationError, match="dictionary"):
            adapter.load_yaml("list.yaml")

    def test_load_yaml_empty_file(self, tmp_path: Path) -> None:
        """Empty YAML file should return empty dict."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        adapter = FileSystemAdapter(tmp_path)
        result = adapter.load_yaml("empty.yaml")

        assert result == {}

    def test_save_yaml(self, tmp_path: Path) -> None:
        """Data should be saved as valid YAML."""
        adapter = FileSystemAdapter(tmp_path)
        data = {"key": "value", "list": [1, 2, 3]}

        adapter.save_yaml("output.yaml", data)

        # Verify by loading back
        with open(tmp_path / "output.yaml") as f:
            loaded = yaml.safe_load(f)

        assert loaded == data

    def test_save_yaml_creates_dirs(self, tmp_path: Path) -> None:
        """save_yaml should create parent directories."""
        adapter = FileSystemAdapter(tmp_path)
        data = {"test": True}

        adapter.save_yaml("subdir/nested/config.yaml", data, create_dirs=True)

        assert (tmp_path / "subdir/nested/config.yaml").exists()


class TestFileSystemAdapterJSON:
    """Test JSON loading and saving."""

    def test_load_json_valid(self, tmp_path: Path) -> None:
        """Valid JSON should load successfully."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "test", "count": 42}')

        adapter = FileSystemAdapter(tmp_path)
        result = adapter.load_json("config.json")

        assert result["name"] == "test"
        assert result["count"] == 42

    def test_load_json_invalid(self, tmp_path: Path) -> None:
        """Invalid JSON should raise ConfigurationError."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{invalid json}")

        adapter = FileSystemAdapter(tmp_path)

        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            adapter.load_json("invalid.json")

    def test_save_json(self, tmp_path: Path) -> None:
        """Data should be saved as valid JSON."""
        adapter = FileSystemAdapter(tmp_path)
        data = {"key": "value", "number": 123}

        adapter.save_json("output.json", data)

        with open(tmp_path / "output.json") as f:
            loaded = json.load(f)

        assert loaded == data


class TestFileSystemAdapterUtilities:
    """Test utility methods."""

    def test_exists(self, tmp_path: Path) -> None:
        """exists should check file presence."""
        (tmp_path / "existing.txt").write_text("content")

        adapter = FileSystemAdapter(tmp_path)

        assert adapter.exists("existing.txt") is True
        assert adapter.exists("nonexistent.txt") is False

    def test_compute_hash(self, tmp_path: Path) -> None:
        """compute_hash should return SHA-256 hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        adapter = FileSystemAdapter(tmp_path)
        hash_value = adapter.compute_hash("test.txt")

        # Known SHA-256 of "hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert hash_value == expected

    def test_validate_hash(self, tmp_path: Path) -> None:
        """validate_hash should verify file integrity."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        adapter = FileSystemAdapter(tmp_path)
        correct_hash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        assert adapter.validate_hash("test.txt", correct_hash) is True
        assert adapter.validate_hash("test.txt", wrong_hash) is False

    def test_list_files(self, tmp_path: Path) -> None:
        """list_files should return matching files."""
        (tmp_path / "file1.yaml").write_text("")
        (tmp_path / "file2.yaml").write_text("")
        (tmp_path / "file3.json").write_text("")

        adapter = FileSystemAdapter(tmp_path)

        yaml_files = adapter.list_files(".", "*.yaml")
        all_files = adapter.list_files(".", "*")

        assert len(yaml_files) == 2
        assert len(all_files) == 3

    def test_absolute_path(self, tmp_path: Path) -> None:
        """Absolute paths should work correctly."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value")

        adapter = FileSystemAdapter()  # No base path
        result = adapter.load_yaml(str(yaml_file))

        assert result["key"] == "value"
