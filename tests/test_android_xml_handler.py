#!/usr/bin/env python3
"""
Comprehensive tests for AndroidXmlHandler.

Tests verify:
1. Array indices use `.0`, `.1` notation (not `[0]`, `[1]`)
2. Plural separator uses `#plural#` (not `:`)
3. Reconstruction preserves structure
4. Round-trip integrity
"""

import sys
sys.path.insert(0, '/Users/yigitkonur/dev/my-cli-apps/srt-translator')

from xlat.format_handlers.android_xml import AndroidXmlHandler


TEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">My App</string>
    <string-array name="colors">
        <item>Red</item>
        <item>Green</item>
        <item>Blue</item>
    </string-array>
    <plurals name="items_count">
        <item quantity="one">%d item</item>
        <item quantity="other">%d items</item>
    </plurals>
</resources>"""


def test_array_indices_use_dot_notation():
    """Test that string-array entries use .0, .1, .2 notation (not [0], [1], [2])."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Find array entries
    array_entries = [e for e in entries if e.metadata.get('type') == 'array']

    # Check IDs
    array_ids = [e.id for e in array_entries]
    expected_ids = ['colors.0', 'colors.1', 'colors.2']

    # Verify dot notation is used
    for expected_id in expected_ids:
        if expected_id not in array_ids:
            print(f"FAIL: test_array_indices_use_dot_notation - Expected '{expected_id}' not found in {array_ids}")
            return False

    # Verify bracket notation is NOT used
    for aid in array_ids:
        if '[' in aid or ']' in aid:
            print(f"FAIL: test_array_indices_use_dot_notation - Found bracket notation in '{aid}'")
            return False

    print("PASS: test_array_indices_use_dot_notation")
    return True


def test_plural_separator_uses_hash_notation():
    """Test that plural entries use #plural# separator (not :)."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Find plural entries
    plural_entries = [e for e in entries if e.metadata.get('type') == 'plural']

    # Check IDs
    plural_ids = [e.id for e in plural_entries]
    expected_ids = ['items_count#plural#one', 'items_count#plural#other']

    # Verify #plural# separator is used
    for expected_id in expected_ids:
        if expected_id not in plural_ids:
            print(f"FAIL: test_plural_separator_uses_hash_notation - Expected '{expected_id}' not found in {plural_ids}")
            return False

    # Verify colon separator is NOT used
    for pid in plural_ids:
        if pid.count(':') > 0 and '#plural#' not in pid:
            print(f"FAIL: test_plural_separator_uses_hash_notation - Found colon separator in '{pid}'")
            return False

    print("PASS: test_plural_separator_uses_hash_notation")
    return True


def test_array_reconstruction():
    """Test that arrays are properly reconstructed with translations."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Create translations for array items
    translations = {
        'app_name': 'Mi Aplicacion',
        'colors.0': 'Rojo',
        'colors.1': 'Verde',
        'colors.2': 'Azul',
        'items_count#plural#one': '%d elemento',
        'items_count#plural#other': '%d elementos',
    }

    # Reconstruct
    result = handler.reconstruct(entries, translations)

    # Verify array structure is present
    if '<string-array name="colors">' not in result:
        print(f"FAIL: test_array_reconstruction - Missing string-array element")
        return False

    # Verify translated items
    if '<item>Rojo</item>' not in result:
        print(f"FAIL: test_array_reconstruction - Missing translated 'Rojo'")
        return False
    if '<item>Verde</item>' not in result:
        print(f"FAIL: test_array_reconstruction - Missing translated 'Verde'")
        return False
    if '<item>Azul</item>' not in result:
        print(f"FAIL: test_array_reconstruction - Missing translated 'Azul'")
        return False

    print("PASS: test_array_reconstruction")
    return True


def test_plural_reconstruction():
    """Test that plurals are properly reconstructed with translations."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Create translations for plural items
    translations = {
        'app_name': 'Mi Aplicacion',
        'colors.0': 'Rojo',
        'colors.1': 'Verde',
        'colors.2': 'Azul',
        'items_count#plural#one': '%d elemento',
        'items_count#plural#other': '%d elementos',
    }

    # Reconstruct
    result = handler.reconstruct(entries, translations)

    # Verify plurals structure is present
    if '<plurals name="items_count">' not in result:
        print(f"FAIL: test_plural_reconstruction - Missing plurals element")
        return False

    # Verify translated items with quantities
    if '<item quantity="one">%d elemento</item>' not in result:
        print(f"FAIL: test_plural_reconstruction - Missing translated 'one' quantity")
        return False
    if '<item quantity="other">%d elementos</item>' not in result:
        print(f"FAIL: test_plural_reconstruction - Missing translated 'other' quantity")
        return False

    print("PASS: test_plural_reconstruction")
    return True


def test_round_trip_preserves_structure():
    """Test that parsing and reconstructing preserves all structure."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Use original texts (no translation)
    translations = {e.id: e.text for e in entries}

    # Reconstruct
    result = handler.reconstruct(entries, translations)

    # Verify all main elements are present
    checks = [
        ('<string name="app_name">My App</string>', 'app_name string'),
        ('<string-array name="colors">', 'colors array start'),
        ('</string-array>', 'array end'),
        ('<item>Red</item>', 'Red item'),
        ('<item>Green</item>', 'Green item'),
        ('<item>Blue</item>', 'Blue item'),
        ('<plurals name="items_count">', 'plurals start'),
        ('</plurals>', 'plurals end'),
        ('<item quantity="one">%d item</item>', 'one quantity'),
        ('<item quantity="other">%d items</item>', 'other quantity'),
    ]

    for content, desc in checks:
        if content not in result:
            print(f"FAIL: test_round_trip_preserves_structure - Missing {desc}")
            return False

    print("PASS: test_round_trip_preserves_structure")
    return True


def test_array_metadata_correct():
    """Test that array entries have correct metadata."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Find array entries
    array_entries = [e for e in entries if e.metadata.get('type') == 'array']

    # Check each entry has correct metadata
    for i, entry in enumerate(sorted(array_entries, key=lambda e: e.id)):
        expected_name = 'colors'
        expected_index = i

        if entry.metadata.get('array_name') != expected_name:
            print(f"FAIL: test_array_metadata_correct - Wrong array_name for {entry.id}")
            return False
        if entry.metadata.get('index') != expected_index:
            print(f"FAIL: test_array_metadata_correct - Wrong index for {entry.id}, expected {expected_index}, got {entry.metadata.get('index')}")
            return False

    print("PASS: test_array_metadata_correct")
    return True


def test_plural_metadata_correct():
    """Test that plural entries have correct metadata."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Find plural entries
    plural_entries = [e for e in entries if e.metadata.get('type') == 'plural']

    # Check metadata
    for entry in plural_entries:
        if entry.metadata.get('plural_name') != 'items_count':
            print(f"FAIL: test_plural_metadata_correct - Wrong plural_name for {entry.id}")
            return False

        quantity = entry.metadata.get('quantity')
        if quantity not in ['one', 'other']:
            print(f"FAIL: test_plural_metadata_correct - Invalid quantity '{quantity}' for {entry.id}")
            return False

    print("PASS: test_plural_metadata_correct")
    return True


def test_entry_text_extraction():
    """Test that text is correctly extracted from all entry types."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    # Build id -> text map
    text_map = {e.id: e.text for e in entries}

    expected = {
        'app_name': 'My App',
        'colors.0': 'Red',
        'colors.1': 'Green',
        'colors.2': 'Blue',
        'items_count#plural#one': '%d item',
        'items_count#plural#other': '%d items',
    }

    for entry_id, expected_text in expected.items():
        actual_text = text_map.get(entry_id)
        if actual_text != expected_text:
            print(f"FAIL: test_entry_text_extraction - For '{entry_id}', expected '{expected_text}', got '{actual_text}'")
            return False

    print("PASS: test_entry_text_extraction")
    return True


def test_no_bracket_notation_anywhere():
    """Ensure no entry ID contains bracket notation [x]."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    for entry in entries:
        if '[' in entry.id or ']' in entry.id:
            print(f"FAIL: test_no_bracket_notation_anywhere - Found bracket in '{entry.id}'")
            return False

    print("PASS: test_no_bracket_notation_anywhere")
    return True


def test_no_colon_separator_in_plurals():
    """Ensure plural IDs use #plural# not : separator."""
    handler = AndroidXmlHandler()
    entries = handler.parse(TEST_XML)

    plural_entries = [e for e in entries if e.metadata.get('type') == 'plural']

    for entry in plural_entries:
        # ID should contain #plural# and NOT have format name:quantity
        if '#plural#' not in entry.id:
            print(f"FAIL: test_no_colon_separator_in_plurals - Missing #plural# in '{entry.id}'")
            return False

        # Check it's not using old colon format like "items_count:one"
        parts = entry.id.split('#plural#')
        if len(parts) != 2:
            print(f"FAIL: test_no_colon_separator_in_plurals - Invalid ID structure '{entry.id}'")
            return False

    print("PASS: test_no_colon_separator_in_plurals")
    return True


def run_all_tests():
    """Run all tests and report summary."""
    print("=" * 60)
    print("Android XML Handler Tests")
    print("=" * 60)
    print()

    tests = [
        test_array_indices_use_dot_notation,
        test_plural_separator_uses_hash_notation,
        test_array_reconstruction,
        test_plural_reconstruction,
        test_round_trip_preserves_structure,
        test_array_metadata_correct,
        test_plural_metadata_correct,
        test_entry_text_extraction,
        test_no_bracket_notation_anywhere,
        test_no_colon_separator_in_plurals,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__} - Exception: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
