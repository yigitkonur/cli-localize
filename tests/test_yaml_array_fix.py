#!/usr/bin/env python3
"""
Test to verify YAML handler array notation fix.

Tests that arrays are flattened with .0, .1 notation instead of [0], [1].
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from xlat.format_handlers.yaml_handler import YamlHandler


def test_array_flattening():
    """Test that arrays are flattened with dot notation."""
    print("Test 1: Array flattening with .0, .1 notation")
    print("=" * 60)

    yaml_content = """
en:
  messages:
    - "First message"
    - "Second message"
    - "Third message"
  user:
    notifications:
      - "You have a new message"
      - "Your order has shipped"
"""

    handler = YamlHandler()
    entries = handler.parse(yaml_content)

    print("\nParsed entries:")
    for entry in entries:
        print(f"  ID: {entry.id}")
        print(f"  Path: {entry.metadata['path']}")
        print(f"  Text: {entry.text}")
        print()

    # Verify notation
    expected_ids = [
        "en.messages.0",
        "en.messages.1",
        "en.messages.2",
        "en.user.notifications.0",
        "en.user.notifications.1",
    ]

    actual_ids = [entry.id for entry in entries]

    print("Expected IDs:")
    for id in expected_ids:
        print(f"  {id}")

    print("\nActual IDs:")
    for id in actual_ids:
        print(f"  {id}")

    # Check for bracket notation (should NOT exist)
    bracket_found = any('[' in entry.id for entry in entries)
    if bracket_found:
        print("\n❌ FAIL: Found bracket notation in IDs!")
        print("  Entries with brackets:")
        for entry in entries:
            if '[' in entry.id:
                print(f"    {entry.id}")
        return False

    # Check for dot notation (should exist)
    dot_notation_found = all(id in actual_ids for id in expected_ids)
    if not dot_notation_found:
        print("\n❌ FAIL: Expected dot notation IDs not found!")
        missing = [id for id in expected_ids if id not in actual_ids]
        print(f"  Missing: {missing}")
        return False

    print("\n✅ PASS: Arrays use dot notation (.0, .1, .2)")
    return True


def test_array_reconstruction():
    """Test that arrays can be reconstructed correctly."""
    print("\n\nTest 2: Array reconstruction")
    print("=" * 60)

    yaml_content = """
en:
  items:
    - "Apple"
    - "Banana"
    - "Cherry"
  nested:
    data:
      - "Value 1"
      - "Value 2"
"""

    handler = YamlHandler()
    entries = handler.parse(yaml_content)

    # Create translations (just modify the text)
    translations = {
        entry.id: entry.text.upper()
        for entry in entries
    }

    print("\nOriginal entries:")
    for entry in entries:
        print(f"  {entry.id}: {entry.text}")

    print("\nTranslations:")
    for id, text in translations.items():
        print(f"  {id}: {text}")

    # Reconstruct
    reconstructed = handler.reconstruct(entries, translations)

    print("\nReconstructed YAML:")
    print(reconstructed)

    # Verify it parses back correctly
    re_parsed = handler.parse(reconstructed)

    print("\nRe-parsed entries:")
    for entry in re_parsed:
        print(f"  {entry.id}: {entry.text}")

    # Check that IDs match
    original_ids = sorted([e.id for e in entries])
    reparsed_ids = sorted([e.id for e in re_parsed])

    if original_ids != reparsed_ids:
        print("\n❌ FAIL: IDs don't match after round-trip!")
        print(f"  Original: {original_ids}")
        print(f"  Re-parsed: {reparsed_ids}")
        return False

    # Check that translations were applied
    for entry in re_parsed:
        expected_text = translations[entry.id]
        if entry.text != expected_text:
            print(f"\n❌ FAIL: Text mismatch for {entry.id}")
            print(f"  Expected: {expected_text}")
            print(f"  Got: {entry.text}")
            return False

    print("\n✅ PASS: Round-trip reconstruction preserves data")
    return True


def test_ibf_compatibility():
    """Test that the notation doesn't conflict with IBF [id] syntax."""
    print("\n\nTest 3: IBF format compatibility")
    print("=" * 60)

    yaml_content = """
en:
  buttons:
    - "[submit] Submit"
    - "[cancel] Cancel"
    - "[save] Save"
"""

    handler = YamlHandler()
    entries = handler.parse(yaml_content)

    print("\nParsed entries with [id] syntax in text:")
    for entry in entries:
        print(f"  ID: {entry.id}")
        print(f"  Text: {entry.text}")
        print()

    # Verify that [id] in TEXT is preserved, but array indices use .0, .1
    expected_ids = [
        "en.buttons.0",
        "en.buttons.1",
        "en.buttons.2",
    ]

    actual_ids = [entry.id for entry in entries]

    # Check IDs use dot notation
    if actual_ids != expected_ids:
        print("❌ FAIL: IDs don't match expected dot notation!")
        print(f"  Expected: {expected_ids}")
        print(f"  Got: {actual_ids}")
        return False

    # Check that [id] in text is preserved
    for entry in entries:
        if not entry.text.startswith('['):
            print(f"❌ FAIL: [id] syntax in text was corrupted!")
            print(f"  Entry: {entry.id}")
            print(f"  Text: {entry.text}")
            return False

    print("✅ PASS: Array indices use .0, .1 while [id] in text is preserved")
    return True


def main():
    """Run all tests."""
    print("YAML Array Notation Fix Tests")
    print("=" * 60)
    print()

    results = []

    try:
        results.append(("Array Flattening", test_array_flattening()))
        results.append(("Array Reconstruction", test_array_reconstruction()))
        results.append(("IBF Compatibility", test_ibf_compatibility()))
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
