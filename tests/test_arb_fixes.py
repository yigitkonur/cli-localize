#!/usr/bin/env python3
"""
Comprehensive tests for ARB format handler fixes.

Tests:
1. Parse ARB with @@ metadata, verify file_metadata is captured
2. Reconstruct with target_language='tr', verify @@locale is 'tr'
3. Reconstruct without target_language, verify original @@locale preserved
4. Test ICU validation detects invalid plural keywords
5. Test @key metadata is preserved
"""

import sys
sys.path.insert(0, '/Users/yigitkonur/dev/my-cli-apps/srt-translator')

from xlat.format_handlers.arb import ArbHandler
import json


def test_parse_captures_file_metadata():
    """Test 1: Parse ARB with @@ metadata, verify file_metadata is captured."""
    handler = ArbHandler()

    arb_content = json.dumps({
        "@@locale": "en",
        "@@context": "My App",
        "@@author": "Test",
        "welcomeMessage": "Welcome, {name}!",
        "@welcomeMessage": {
            "description": "Welcome message",
            "placeholders": {"name": {"type": "String"}}
        },
        "itemCount": "{count, plural, =0{No items} =1{One item} other{{count} items}}"
    }, indent=2)

    entries = handler.parse(arb_content)

    # Check that file_metadata is captured in each entry
    if not entries:
        print("FAIL: test_parse_captures_file_metadata - No entries parsed")
        return False

    file_metadata = entries[0].metadata.get('file_metadata', {})

    expected_keys = {'@@locale', '@@context', '@@author'}
    actual_keys = set(file_metadata.keys())

    if expected_keys != actual_keys:
        print(f"FAIL: test_parse_captures_file_metadata - Expected keys {expected_keys}, got {actual_keys}")
        return False

    if file_metadata.get('@@locale') != 'en':
        print(f"FAIL: test_parse_captures_file_metadata - @@locale should be 'en', got '{file_metadata.get('@@locale')}'")
        return False

    if file_metadata.get('@@context') != 'My App':
        print(f"FAIL: test_parse_captures_file_metadata - @@context should be 'My App', got '{file_metadata.get('@@context')}'")
        return False

    if file_metadata.get('@@author') != 'Test':
        print(f"FAIL: test_parse_captures_file_metadata - @@author should be 'Test', got '{file_metadata.get('@@author')}'")
        return False

    print("PASS: test_parse_captures_file_metadata")
    return True


def test_reconstruct_with_target_language():
    """Test 2: Reconstruct with target_language='tr', verify @@locale is 'tr'."""
    handler = ArbHandler()

    arb_content = json.dumps({
        "@@locale": "en",
        "@@context": "My App",
        "@@author": "Test",
        "welcomeMessage": "Welcome, {name}!",
        "@welcomeMessage": {
            "description": "Welcome message",
            "placeholders": {"name": {"type": "String"}}
        }
    }, indent=2)

    entries = handler.parse(arb_content)
    translations = {"welcomeMessage": "Hosgeldiniz, {name}!"}

    result = handler.reconstruct(entries, translations, target_language='tr')
    result_data = json.loads(result)

    if result_data.get('@@locale') != 'tr':
        print(f"FAIL: test_reconstruct_with_target_language - @@locale should be 'tr', got '{result_data.get('@@locale')}'")
        return False

    # Verify other @@ metadata is preserved
    if result_data.get('@@context') != 'My App':
        print(f"FAIL: test_reconstruct_with_target_language - @@context should be preserved, got '{result_data.get('@@context')}'")
        return False

    if result_data.get('@@author') != 'Test':
        print(f"FAIL: test_reconstruct_with_target_language - @@author should be preserved, got '{result_data.get('@@author')}'")
        return False

    print("PASS: test_reconstruct_with_target_language")
    return True


def test_reconstruct_without_target_language():
    """Test 3: Reconstruct without target_language, verify original @@locale preserved."""
    handler = ArbHandler()

    arb_content = json.dumps({
        "@@locale": "en",
        "@@context": "My App",
        "welcomeMessage": "Welcome, {name}!"
    }, indent=2)

    entries = handler.parse(arb_content)
    translations = {"welcomeMessage": "Translated welcome"}

    result = handler.reconstruct(entries, translations)  # No target_language
    result_data = json.loads(result)

    if result_data.get('@@locale') != 'en':
        print(f"FAIL: test_reconstruct_without_target_language - @@locale should be 'en' (original), got '{result_data.get('@@locale')}'")
        return False

    print("PASS: test_reconstruct_without_target_language")
    return True


def test_icu_validation_detects_invalid_plural_keywords():
    """Test 4: Test ICU validation detects invalid plural keywords."""
    handler = ArbHandler()

    # Valid plural message
    valid_message = "{count, plural, =0{No items} =1{One item} other{{count} items}}"
    errors = handler.validate_icu_message(valid_message)
    if errors:
        print(f"FAIL: test_icu_validation_detects_invalid_plural_keywords - Valid message flagged: {errors}")
        return False

    # Invalid plural keyword 'invalid'
    invalid_message = "{count, plural, invalid{Bad} other{OK}}"
    errors = handler.validate_icu_message(invalid_message)
    if not errors:
        print("FAIL: test_icu_validation_detects_invalid_plural_keywords - Invalid keyword 'invalid' not detected")
        return False

    # Check that 'invalid' is in the error message
    error_text = str(errors)
    if 'invalid' not in error_text.lower():
        print(f"FAIL: test_icu_validation_detects_invalid_plural_keywords - Error should mention 'invalid', got: {errors}")
        return False

    # Test with valid standard plural keywords
    standard_valid = "{count, plural, zero{No items} one{{count} item} two{Two items} few{Few items} many{Many items} other{{count} items}}"
    errors = handler.validate_icu_message(standard_valid)
    keyword_errors = [e for e in errors if 'keyword' in e.lower()]
    if keyword_errors:
        print(f"FAIL: test_icu_validation_detects_invalid_plural_keywords - Valid keywords flagged: {keyword_errors}")
        return False

    # Test with numeric keywords (=N format)
    numeric_valid = "{count, plural, =0{None} =1{One} =5{Five} other{Many}}"
    errors = handler.validate_icu_message(numeric_valid)
    keyword_errors = [e for e in errors if 'keyword' in e.lower()]
    if keyword_errors:
        print(f"FAIL: test_icu_validation_detects_invalid_plural_keywords - Numeric keywords flagged: {keyword_errors}")
        return False

    print("PASS: test_icu_validation_detects_invalid_plural_keywords")
    return True


def test_key_metadata_preserved():
    """Test 5: Test @key metadata is preserved."""
    handler = ArbHandler()

    arb_content = json.dumps({
        "@@locale": "en",
        "welcomeMessage": "Welcome, {name}!",
        "@welcomeMessage": {
            "description": "Welcome message",
            "placeholders": {
                "name": {"type": "String", "example": "John"}
            }
        },
        "itemCount": "{count, plural, =0{No items} =1{One item} other{{count} items}}",
        "@itemCount": {
            "description": "Number of items in cart",
            "placeholders": {
                "count": {"type": "int"}
            }
        }
    }, indent=2)

    entries = handler.parse(arb_content)
    translations = {
        "welcomeMessage": "Hosgeldiniz, {name}!",
        "itemCount": "{count, plural, =0{Oge yok} =1{Bir oge} other{{count} oge}}"
    }

    result = handler.reconstruct(entries, translations, target_language='tr')
    result_data = json.loads(result)

    # Check @welcomeMessage metadata
    if '@welcomeMessage' not in result_data:
        print("FAIL: test_key_metadata_preserved - @welcomeMessage metadata missing")
        return False

    welcome_meta = result_data['@welcomeMessage']
    if welcome_meta.get('description') != "Welcome message":
        print(f"FAIL: test_key_metadata_preserved - @welcomeMessage description wrong: {welcome_meta.get('description')}")
        return False

    if 'placeholders' not in welcome_meta:
        print("FAIL: test_key_metadata_preserved - @welcomeMessage placeholders missing")
        return False

    if welcome_meta['placeholders'].get('name', {}).get('type') != 'String':
        print("FAIL: test_key_metadata_preserved - @welcomeMessage placeholder type wrong")
        return False

    # Check @itemCount metadata
    if '@itemCount' not in result_data:
        print("FAIL: test_key_metadata_preserved - @itemCount metadata missing")
        return False

    item_meta = result_data['@itemCount']
    if item_meta.get('description') != "Number of items in cart":
        print(f"FAIL: test_key_metadata_preserved - @itemCount description wrong: {item_meta.get('description')}")
        return False

    print("PASS: test_key_metadata_preserved")
    return True


def test_all_double_at_keys_in_output():
    """Test 6: Verify all @@ keys are in output."""
    handler = ArbHandler()

    arb_content = json.dumps({
        "@@locale": "en",
        "@@context": "My App",
        "@@author": "Test",
        "@@last_modified": "2025-01-16",
        "welcomeMessage": "Welcome, {name}!",
        "@welcomeMessage": {
            "description": "Welcome message",
            "placeholders": {"name": {"type": "String"}}
        },
        "itemCount": "{count, plural, =0{No items} =1{One item} other{{count} items}}"
    }, indent=2)

    entries = handler.parse(arb_content)
    translations = {
        "welcomeMessage": "Hosgeldiniz, {name}!",
        "itemCount": "{count, plural, =0{Oge yok} =1{Bir oge} other{{count} oge}}"
    }

    result = handler.reconstruct(entries, translations, target_language='tr')
    result_data = json.loads(result)

    # Check all @@ keys are present
    expected_double_at_keys = ['@@locale', '@@context', '@@author', '@@last_modified']
    missing_keys = []

    for key in expected_double_at_keys:
        if key not in result_data:
            missing_keys.append(key)

    if missing_keys:
        print(f"FAIL: test_all_double_at_keys_in_output - Missing @@ keys: {missing_keys}")
        return False

    # Verify @@locale is updated to 'tr' but others are preserved
    if result_data['@@locale'] != 'tr':
        print(f"FAIL: test_all_double_at_keys_in_output - @@locale should be 'tr', got '{result_data['@@locale']}'")
        return False

    if result_data['@@context'] != 'My App':
        print(f"FAIL: test_all_double_at_keys_in_output - @@context should be preserved")
        return False

    if result_data['@@author'] != 'Test':
        print(f"FAIL: test_all_double_at_keys_in_output - @@author should be preserved")
        return False

    if result_data['@@last_modified'] != '2025-01-16':
        print(f"FAIL: test_all_double_at_keys_in_output - @@last_modified should be preserved")
        return False

    print("PASS: test_all_double_at_keys_in_output")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("ARB Format Handler Tests")
    print("=" * 60)
    print()

    tests = [
        test_parse_captures_file_metadata,
        test_reconstruct_with_target_language,
        test_reconstruct_without_target_language,
        test_icu_validation_detects_invalid_plural_keywords,
        test_key_metadata_preserved,
        test_all_double_at_keys_in_output,
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
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
