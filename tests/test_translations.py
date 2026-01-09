"""Test translation file completeness."""

import json
from pathlib import Path

import pytest

TRANSLATIONS_PATH = Path(__file__).parent.parent / "custom_components" / "alfen_wallbox" / "translations"
STRINGS_PATH = Path(__file__).parent.parent / "custom_components" / "alfen_wallbox" / "strings.json"


def get_all_keys(data: dict, prefix: str = "") -> set[str]:
    """Recursively get all keys from a nested dictionary.

    Args:
        data: The dictionary to extract keys from
        prefix: The current key prefix for nested keys

    Returns:
        A set of all keys in dot notation (e.g., "config.step.user.title")
    """
    keys = set()
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.update(get_all_keys(value, full_key))
        else:
            keys.add(full_key)
    return keys


def load_json_file(path: Path) -> dict:
    """Load a JSON file and return its contents."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_translation_files() -> list[Path]:
    """Get all translation files except en.json (the reference)."""
    return [f for f in TRANSLATIONS_PATH.glob("*.json") if f.name != "en.json"]


class TestTranslationCompleteness:
    """Tests for translation file completeness."""

    def test_strings_json_exists(self):
        """Test that strings.json exists."""
        assert STRINGS_PATH.exists(), "strings.json should exist"

    def test_english_translation_exists(self):
        """Test that en.json exists."""
        en_path = TRANSLATIONS_PATH / "en.json"
        assert en_path.exists(), "en.json should exist"

    def test_strings_json_matches_english(self):
        """Test that strings.json and en.json have the same keys."""
        strings_data = load_json_file(STRINGS_PATH)
        en_data = load_json_file(TRANSLATIONS_PATH / "en.json")

        strings_keys = get_all_keys(strings_data)
        en_keys = get_all_keys(en_data)

        missing_in_en = strings_keys - en_keys
        extra_in_en = en_keys - strings_keys

        assert not missing_in_en, f"Keys in strings.json but missing in en.json: {missing_in_en}"
        assert not extra_in_en, f"Keys in en.json but missing in strings.json: {extra_in_en}"

    def test_all_translation_files_exist(self):
        """Test that expected translation files exist."""
        expected_languages = ["en", "nl", "de", "fr", "es", "it", "sv", "no", "da"]

        for lang in expected_languages:
            path = TRANSLATIONS_PATH / f"{lang}.json"
            assert path.exists(), f"Translation file {lang}.json should exist"

    @pytest.mark.parametrize("translation_file", get_translation_files(), ids=lambda p: p.name)
    def test_translation_has_all_keys(self, translation_file: Path):
        """Test that each translation file has all required keys from en.json."""
        en_data = load_json_file(TRANSLATIONS_PATH / "en.json")
        trans_data = load_json_file(translation_file)

        en_keys = get_all_keys(en_data)
        trans_keys = get_all_keys(trans_data)

        missing_keys = en_keys - trans_keys

        assert not missing_keys, (
            f"Translation {translation_file.name} is missing {len(missing_keys)} keys:\n"
            + "\n".join(sorted(missing_keys)[:20])  # Show first 20 missing keys
            + (f"\n... and {len(missing_keys) - 20} more" if len(missing_keys) > 20 else "")
        )

    @pytest.mark.parametrize("translation_file", get_translation_files(), ids=lambda p: p.name)
    def test_translation_has_no_extra_keys(self, translation_file: Path):
        """Test that translation files don't have extra keys not in en.json."""
        en_data = load_json_file(TRANSLATIONS_PATH / "en.json")
        trans_data = load_json_file(translation_file)

        en_keys = get_all_keys(en_data)
        trans_keys = get_all_keys(trans_data)

        extra_keys = trans_keys - en_keys

        assert not extra_keys, (
            f"Translation {translation_file.name} has {len(extra_keys)} extra keys:\n"
            + "\n".join(sorted(extra_keys)[:20])
            + (f"\n... and {len(extra_keys) - 20} more" if len(extra_keys) > 20 else "")
        )


class TestTranslationStructure:
    """Tests for translation file structure."""

    def test_strings_json_valid_json(self):
        """Test that strings.json is valid JSON."""
        try:
            load_json_file(STRINGS_PATH)
        except json.JSONDecodeError as e:
            pytest.fail(f"strings.json is not valid JSON: {e}")

    @pytest.mark.parametrize("translation_file", list(TRANSLATIONS_PATH.glob("*.json")), ids=lambda p: p.name)
    def test_translation_valid_json(self, translation_file: Path):
        """Test that each translation file is valid JSON."""
        try:
            load_json_file(translation_file)
        except json.JSONDecodeError as e:
            pytest.fail(f"{translation_file.name} is not valid JSON: {e}")

    def test_strings_json_has_required_sections(self):
        """Test that strings.json has all required top-level sections."""
        data = load_json_file(STRINGS_PATH)

        required_sections = ["config", "options", "services", "entity", "issues"]

        for section in required_sections:
            assert section in data, f"strings.json should have '{section}' section"

    def test_english_has_all_entity_types(self):
        """Test that en.json has translations for all entity types."""
        data = load_json_file(TRANSLATIONS_PATH / "en.json")

        entity_types = ["sensor", "binary_sensor", "number", "select", "switch", "button", "text"]

        assert "entity" in data, "en.json should have 'entity' section"

        for entity_type in entity_types:
            assert entity_type in data["entity"], f"en.json should have entity.{entity_type} section"


class TestTranslationQuality:
    """Tests for translation quality metrics."""

    def test_translation_completeness_report(self):
        """Generate a completeness report for all translations."""
        en_data = load_json_file(TRANSLATIONS_PATH / "en.json")
        en_keys = get_all_keys(en_data)
        total_keys = len(en_keys)

        report = []
        report.append(f"Translation Completeness Report")
        report.append(f"Total keys in en.json: {total_keys}")
        report.append("-" * 50)

        for trans_file in sorted(TRANSLATIONS_PATH.glob("*.json")):
            trans_data = load_json_file(trans_file)
            trans_keys = get_all_keys(trans_data)

            matching_keys = en_keys & trans_keys
            completeness = len(matching_keys) / total_keys * 100

            report.append(f"{trans_file.name}: {completeness:.1f}% ({len(matching_keys)}/{total_keys} keys)")

        # This test always passes but prints the report
        print("\n" + "\n".join(report))

    def test_no_empty_translations(self):
        """Test that translation values are not empty strings."""
        empty_values = []

        for trans_file in TRANSLATIONS_PATH.glob("*.json"):
            data = load_json_file(trans_file)
            keys = get_all_keys(data)

            for key in keys:
                # Navigate to the value
                parts = key.split(".")
                value = data
                for part in parts:
                    value = value[part]

                if value == "":
                    empty_values.append(f"{trans_file.name}: {key}")

        assert not empty_values, (
            f"Found {len(empty_values)} empty translation values:\n"
            + "\n".join(empty_values[:20])
            + (f"\n... and {len(empty_values) - 20} more" if len(empty_values) > 20 else "")
        )
