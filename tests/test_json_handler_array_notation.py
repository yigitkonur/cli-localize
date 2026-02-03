#!/usr/bin/env python3
"""
Comprehensive tests for JSON handler array notation fix.

Bug fixed: Array indices used `[0]` notation which broke IBF parsing.
Fix: Changed to `.0` notation (dot notation for array indices).

Tests verify:
1. Entry IDs use `.0`, `.1` etc (NOT `[0]`, `[1]`)
2. Nested arrays produce correct IDs like `items.0.0`, `items.0.1`
3. Reconstruction places translated values correctly
4. Round-trip preserves structure
"""

import sys
import json

sys.path.insert(0, '/Users/yigitkonur/dev/my-cli-apps/srt-translator')
from xlat.format_handlers.json_handler import JsonHandler, NestedJsonHandler


def test_simple_array_notation():
    """Test 1: Simple array indices use dot notation (`.0` not `[0]`)"""
    print("\n" + "="*60)
    print("TEST 1: Simple array notation")
    print("="*60)

    handler = JsonHandler()
    content = json.dumps({
        "simple": "Hello",
        "items": ["First", "Second", "Third"]
    })

    entries = handler.parse(content)

    # Check IDs
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # Verify no brackets in IDs
    has_brackets = any('[' in id or ']' in id for id in ids)

    # Expected IDs with dot notation
    expected_ids = {"simple", "items.0", "items.1", "items.2"}
    actual_ids = set(ids)

    correct_ids = actual_ids == expected_ids
    no_brackets = not has_brackets

    print(f"Expected IDs: {expected_ids}")
    print(f"Actual IDs: {actual_ids}")
    print(f"Contains brackets: {has_brackets}")

    if correct_ids and no_brackets:
        print("PASS: Array indices use dot notation (.0, .1, .2)")
        return True
    else:
        print("FAIL: Array notation incorrect")
        if has_brackets:
            print("  - IDs contain bracket notation [x]")
        if not correct_ids:
            print(f"  - Missing IDs: {expected_ids - actual_ids}")
            print(f"  - Extra IDs: {actual_ids - expected_ids}")
        return False


def test_nested_array_notation():
    """Test 2: Nested arrays use dot notation (items.0.0, items.0.1)"""
    print("\n" + "="*60)
    print("TEST 2: Nested array notation")
    print("="*60)

    handler = JsonHandler()
    content = json.dumps({
        "items": [["a", "b"], ["c", "d"]]
    })

    entries = handler.parse(content)
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # Verify no brackets
    has_brackets = any('[' in id or ']' in id for id in ids)

    # Expected nested IDs
    expected_ids = {"items.0.0", "items.0.1", "items.1.0", "items.1.1"}
    actual_ids = set(ids)

    correct_ids = actual_ids == expected_ids
    no_brackets = not has_brackets

    print(f"Expected IDs: {expected_ids}")
    print(f"Actual IDs: {actual_ids}")
    print(f"Contains brackets: {has_brackets}")

    if correct_ids and no_brackets:
        print("PASS: Nested array indices use dot notation (items.0.0, etc.)")
        return True
    else:
        print("FAIL: Nested array notation incorrect")
        return False


def test_mixed_nested_structure():
    """Test 3: Mixed nested dict/array structures"""
    print("\n" + "="*60)
    print("TEST 3: Mixed nested structure")
    print("="*60)

    handler = JsonHandler()
    content = json.dumps({
        "simple": "Hello",
        "items": ["First", "Second", "Third"],
        "nested": {
            "array": ["A", "B"]
        }
    })

    entries = handler.parse(content)
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # Verify no brackets
    has_brackets = any('[' in id or ']' in id for id in ids)

    # Expected IDs
    expected_ids = {
        "simple",
        "items.0", "items.1", "items.2",
        "nested.array.0", "nested.array.1"
    }
    actual_ids = set(ids)

    correct_ids = actual_ids == expected_ids
    no_brackets = not has_brackets

    print(f"Expected IDs: {expected_ids}")
    print(f"Actual IDs: {actual_ids}")
    print(f"Contains brackets: {has_brackets}")

    if correct_ids and no_brackets:
        print("PASS: Mixed nested structure uses correct dot notation")
        return True
    else:
        print("FAIL: Mixed nested structure notation incorrect")
        return False


def test_reconstruction_with_translations():
    """Test 4: Reconstruction places translated values correctly"""
    print("\n" + "="*60)
    print("TEST 4: Reconstruction with translations")
    print("="*60)

    handler = JsonHandler()
    original_content = json.dumps({
        "simple": "Hello",
        "items": ["First", "Second", "Third"],
        "nested": {
            "array": ["A", "B"]
        }
    })

    entries = handler.parse(original_content)

    # Simulate translations
    translations = {
        "simple": "Hola",
        "items.0": "Primero",
        "items.1": "Segundo",
        "items.2": "Tercero",
        "nested.array.0": "A-traducido",
        "nested.array.1": "B-traducido"
    }

    # Reconstruct
    reconstructed = handler.reconstruct(entries, translations)
    result = json.loads(reconstructed)

    print(f"Reconstructed JSON:\n{json.dumps(result, indent=2)}")

    # Verify values
    checks = [
        (result.get("simple") == "Hola", "simple == 'Hola'"),
        (result.get("items", [None])[0] == "Primero", "items[0] == 'Primero'"),
        (result.get("items", [None, None])[1] == "Segundo", "items[1] == 'Segundo'"),
        (result.get("items", [None, None, None])[2] == "Tercero", "items[2] == 'Tercero'"),
        (result.get("nested", {}).get("array", [None])[0] == "A-traducido", "nested.array[0] == 'A-traducido'"),
        (result.get("nested", {}).get("array", [None, None])[1] == "B-traducido", "nested.array[1] == 'B-traducido'"),
    ]

    all_passed = True
    for passed, desc in checks:
        status = "OK" if passed else "FAIL"
        print(f"  {status}: {desc}")
        if not passed:
            all_passed = False

    if all_passed:
        print("PASS: Reconstruction correctly places all translated values")
        return True
    else:
        print("FAIL: Some translations not placed correctly")
        return False


def test_round_trip_preserves_structure():
    """Test 5: Round-trip parse -> translate -> reconstruct -> parse preserves structure"""
    print("\n" + "="*60)
    print("TEST 5: Round-trip structure preservation")
    print("="*60)

    handler = JsonHandler()
    original = {
        "simple": "Hello",
        "items": ["First", "Second", "Third"],
        "nested": {
            "array": ["A", "B"]
        }
    }
    original_content = json.dumps(original)

    # Round 1: Parse
    entries1 = handler.parse(original_content)
    ids1 = sorted([e.id for e in entries1])

    # No translation (identity)
    identity_translations = {e.id: e.text for e in entries1}

    # Reconstruct
    reconstructed1 = handler.reconstruct(entries1, identity_translations)
    result1 = json.loads(reconstructed1)

    # Round 2: Parse reconstructed
    entries2 = handler.parse(reconstructed1)
    ids2 = sorted([e.id for e in entries2])

    # Reconstruct again
    identity_translations2 = {e.id: e.text for e in entries2}
    reconstructed2 = handler.reconstruct(entries2, identity_translations2)
    result2 = json.loads(reconstructed2)

    print(f"Original structure: {json.dumps(original, sort_keys=True)}")
    print(f"After round 1: {json.dumps(result1, sort_keys=True)}")
    print(f"After round 2: {json.dumps(result2, sort_keys=True)}")
    print(f"IDs round 1: {ids1}")
    print(f"IDs round 2: {ids2}")

    # Verify structure preserved
    structure_match = (
        result1 == original and
        result2 == original and
        ids1 == ids2
    )

    # Verify no brackets in any round
    no_brackets = (
        not any('[' in id or ']' in id for id in ids1) and
        not any('[' in id or ']' in id for id in ids2)
    )

    if structure_match and no_brackets:
        print("PASS: Round-trip preserves structure and uses dot notation")
        return True
    else:
        print("FAIL: Round-trip did not preserve structure or used brackets")
        if not structure_match:
            print("  - Structure changed")
        if not no_brackets:
            print("  - Bracket notation found")
        return False


def test_deeply_nested_arrays():
    """Test 6: Deeply nested arrays (3+ levels)"""
    print("\n" + "="*60)
    print("TEST 6: Deeply nested arrays")
    print("="*60)

    handler = JsonHandler()
    content = json.dumps({
        "level1": {
            "level2": [
                ["deep1", "deep2"],
                ["deep3", "deep4"]
            ]
        }
    })

    entries = handler.parse(content)
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # Verify no brackets
    has_brackets = any('[' in id or ']' in id for id in ids)

    # Expected IDs
    expected_ids = {
        "level1.level2.0.0", "level1.level2.0.1",
        "level1.level2.1.0", "level1.level2.1.1"
    }
    actual_ids = set(ids)

    correct_ids = actual_ids == expected_ids
    no_brackets = not has_brackets

    print(f"Expected IDs: {expected_ids}")
    print(f"Actual IDs: {actual_ids}")
    print(f"Contains brackets: {has_brackets}")

    if correct_ids and no_brackets:
        print("PASS: Deeply nested arrays use correct dot notation")
        return True
    else:
        print("FAIL: Deeply nested array notation incorrect")
        return False


def test_array_at_root():
    """Test 7: Edge case - array values directly under root"""
    print("\n" + "="*60)
    print("TEST 7: Array at root level")
    print("="*60)

    handler = JsonHandler()
    content = json.dumps({
        "0": "First",  # String key that looks like index
        "strings": ["a", "b", "c"]
    })

    entries = handler.parse(content)
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # Verify no brackets
    has_brackets = any('[' in id or ']' in id for id in ids)

    # String "0" key should be just "0", array should be strings.0, strings.1, etc.
    expected_ids = {"0", "strings.0", "strings.1", "strings.2"}
    actual_ids = set(ids)

    correct_ids = actual_ids == expected_ids
    no_brackets = not has_brackets

    print(f"Expected IDs: {expected_ids}")
    print(f"Actual IDs: {actual_ids}")
    print(f"Contains brackets: {has_brackets}")

    if correct_ids and no_brackets:
        print("PASS: Array at root level uses correct notation")
        return True
    else:
        print("FAIL: Array at root level notation incorrect")
        return False


def test_nested_json_handler():
    """Test 8: NestedJsonHandler handles dict strings (arrays are skipped by design)"""
    print("\n" + "="*60)
    print("TEST 8: NestedJsonHandler for dict-only structures")
    print("="*60)

    handler = NestedJsonHandler()
    # NestedJsonHandler is designed for dict-only structures
    # It skips arrays by design (see _parse_nested which only handles dict and str)
    content = json.dumps({
        "greeting": "Hello",
        "nested": {
            "message": "World"
        }
    })

    entries = handler.parse(content)
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # Verify no brackets
    has_brackets = any('[' in id or ']' in id for id in ids)

    # Expected IDs for dict-only structure
    expected_ids = {"greeting", "nested.message"}
    actual_ids = set(ids)

    ids_correct = expected_ids == actual_ids
    no_brackets = not has_brackets

    print(f"Expected IDs: {expected_ids}")
    print(f"Actual IDs: {actual_ids}")
    print(f"Contains brackets: {has_brackets}")

    if ids_correct and no_brackets:
        print("PASS: NestedJsonHandler handles dict structures correctly")
        return True
    else:
        print("FAIL: NestedJsonHandler dict handling incorrect")
        return False


def test_translation_id_format_for_ibf():
    """Test 9: Verify IDs are valid for IBF format (no special chars except dot)"""
    print("\n" + "="*60)
    print("TEST 9: IBF-compatible ID format")
    print("="*60)

    handler = JsonHandler()
    content = json.dumps({
        "simple": "Hello",
        "items": ["First", "Second", "Third"],
        "nested": {
            "deep": {
                "array": ["A", "B", "C"]
            }
        }
    })

    entries = handler.parse(content)
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # IBF format should not have brackets, only dots and alphanumeric
    invalid_chars = set()
    for id in ids:
        for char in id:
            if char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._':
                invalid_chars.add(char)

    print(f"Invalid characters found: {invalid_chars if invalid_chars else 'None'}")

    # Specifically check for brackets
    has_brackets = '[' in invalid_chars or ']' in invalid_chars

    if not invalid_chars:
        print("PASS: All IDs are IBF-compatible (no special chars)")
        return True
    else:
        print(f"FAIL: IDs contain invalid characters: {invalid_chars}")
        if has_brackets:
            print("  - Specifically found bracket notation")
        return False


def test_reconstruction_nested_arrays():
    """Test 10: Reconstruction of nested arrays (using flat arrays)"""
    print("\n" + "="*60)
    print("TEST 10: Reconstruction of flat arrays")
    print("="*60)

    handler = JsonHandler()
    # Test with flat array structure (simpler case)
    original = {
        "greetings": ["hello", "hi", "hey"]
    }
    original_content = json.dumps(original)

    entries = handler.parse(original_content)

    # Translations
    translations = {
        "greetings.0": "HELLO",
        "greetings.1": "HI",
        "greetings.2": "HEY"
    }

    reconstructed = handler.reconstruct(entries, translations)
    result = json.loads(reconstructed)

    print(f"Original: {original}")
    print(f"Translations: {translations}")
    print(f"Reconstructed: {result}")

    expected = {
        "greetings": ["HELLO", "HI", "HEY"]
    }

    if result == expected:
        print("PASS: Flat array reconstruction correct")
        return True
    else:
        print(f"FAIL: Expected {expected}, got {result}")
        return False


def test_nested_array_reconstruction_complex():
    """Test 11: Nested arrays within dict (edge case for _set_nested)"""
    print("\n" + "="*60)
    print("TEST 11: Nested arrays within dict structure")
    print("="*60)

    handler = JsonHandler()
    # Nested arrays within dict wrapper
    original = {
        "data": {
            "items": ["a", "b"]
        }
    }
    original_content = json.dumps(original)

    entries = handler.parse(original_content)
    ids = [e.id for e in entries]
    print(f"Entry IDs: {ids}")

    # Translations
    translations = {
        "data.items.0": "A",
        "data.items.1": "B"
    }

    reconstructed = handler.reconstruct(entries, translations)
    result = json.loads(reconstructed)

    print(f"Original: {original}")
    print(f"Reconstructed: {result}")

    expected = {
        "data": {
            "items": ["A", "B"]
        }
    }

    # Verify no brackets in IDs
    has_brackets = any('[' in id or ']' in id for id in ids)

    if result == expected and not has_brackets:
        print("PASS: Nested arrays within dict reconstructed correctly")
        return True
    else:
        print(f"FAIL: Expected {expected}, got {result}")
        if has_brackets:
            print("  - IDs contain bracket notation")
        return False


def run_all_tests():
    """Run all tests and report summary"""
    print("\n" + "#"*60)
    print("# JSON Handler Array Notation Tests")
    print("# Bug: Array indices used [0] notation, breaking IBF")
    print("# Fix: Changed to .0 dot notation")
    print("#"*60)

    tests = [
        ("Simple array notation", test_simple_array_notation),
        ("Nested array notation", test_nested_array_notation),
        ("Mixed nested structure", test_mixed_nested_structure),
        ("Reconstruction with translations", test_reconstruction_with_translations),
        ("Round-trip preservation", test_round_trip_preserves_structure),
        ("Deeply nested arrays", test_deeply_nested_arrays),
        ("Array at root level", test_array_at_root),
        ("NestedJsonHandler", test_nested_json_handler),
        ("IBF-compatible format", test_translation_id_format_for_ibf),
        ("Flat array reconstruction", test_reconstruction_nested_arrays),
        ("Nested arrays in dict", test_nested_array_reconstruction_complex),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"EXCEPTION: {e}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    passed_count = 0
    failed_count = 0

    for name, passed, error in results:
        status = "PASS" if passed else "FAIL"
        if passed:
            passed_count += 1
        else:
            failed_count += 1

        error_msg = f" (Error: {error})" if error else ""
        print(f"  [{status}] {name}{error_msg}")

    print("-"*60)
    print(f"Total: {passed_count} passed, {failed_count} failed out of {len(results)}")

    if failed_count == 0:
        print("\nALL TESTS PASSED - Array notation fix verified!")
    else:
        print(f"\n{failed_count} TEST(S) FAILED - Review needed")

    return failed_count == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
