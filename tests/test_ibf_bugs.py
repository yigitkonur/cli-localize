#!/usr/bin/env python3
"""
Comprehensive tests for IBF format bug fixes.

Tests verify:
1. BUG 1: Empty strings - ENTRY_PATTERN allows .* (empty text)
2. BUG 2: Newline escaping in encoder/decoder
3. BUG 3: Multiline round-trip preservation

Run: python test_ibf_bugs.py
"""

import sys
import os

from xlat.ibf_format import IBFEncoder, IBFDecoder, IBFEntry


def test_empty_string_entry():
    """BUG 1: Test that empty string entries encode/decode correctly."""
    print("\n=== TEST 1: Empty String Entry ===")

    encoder = IBFEncoder(context_size=0)
    decoder = IBFDecoder()

    # Create entry with empty text
    entry = IBFEntry('key123', '')

    # Encode
    encoded = encoder.encode_batch(
        entries_to_translate=[entry],
        context_before=[],
        context_after=[],
        batch_num=1,
        total_batches=1
    )

    print(f"Encoded IBF:\n{encoded}")

    # Check that [key123] appears with space after (empty text)
    if "[key123] " not in encoded and "[key123]" not in encoded:
        print("FAIL: Entry ID not found in encoded output")
        return False

    # Now test decoding a translated response with empty text
    translated_response = """#TRANSLATED:v1:batch=1/1:count=1:status=ok
[key123]
---"""

    metadata, decoded = decoder.decode(translated_response)

    if len(decoded) != 1:
        print(f"FAIL: Expected 1 entry, got {len(decoded)}")
        return False

    if decoded[0].id != 'key123':
        print(f"FAIL: Expected ID 'key123', got '{decoded[0].id}'")
        return False

    # Empty text after strip should be empty string
    if decoded[0].text != '':
        print(f"FAIL: Expected empty text, got '{decoded[0].text}'")
        return False

    print("PASS: Empty string entry encodes and decodes correctly")
    return True


def test_multiline_id():
    """BUG 2: Test that IDs with newlines are preserved after encode/decode."""
    print("\n=== TEST 2: Multiline ID ===")

    encoder = IBFEncoder(context_size=0)
    decoder = IBFDecoder()

    # Create entry with newline in ID (like PO msgid)
    original_id = "Line1\nLine2"
    entry = IBFEntry(original_id, 'some text')

    # Encode
    encoded = encoder.encode_batch(
        entries_to_translate=[entry],
        context_before=[],
        context_after=[],
        batch_num=1,
        total_batches=1
    )

    print(f"Encoded IBF:\n{encoded}")

    # Check newline is escaped
    if "\\n" not in encoded:
        print("FAIL: Newline in ID not escaped to \\n")
        return False

    # Simulate translated response with escaped newline in ID
    translated_response = """#TRANSLATED:v1:batch=1/1:count=1:status=ok
[Line1\\nLine2] translated text
---"""

    metadata, decoded = decoder.decode(translated_response)

    if len(decoded) != 1:
        print(f"FAIL: Expected 1 entry, got {len(decoded)}")
        return False

    # ID should have real newline restored
    if decoded[0].id != original_id:
        print(f"FAIL: Expected ID '{repr(original_id)}', got '{repr(decoded[0].id)}'")
        return False

    print(f"Decoded ID: {repr(decoded[0].id)}")
    print("PASS: Multiline ID preserved after encode/decode")
    return True


def test_multiline_text():
    """BUG 3: Test that text with newlines survives encode/decode cycle."""
    print("\n=== TEST 3: Multiline Text ===")

    encoder = IBFEncoder(context_size=0)
    decoder = IBFDecoder()

    # Create entry with newline in text (SRT multiline subtitle)
    original_text = "First line\nSecond line"
    entry = IBFEntry('1', original_text)

    # Encode
    encoded = encoder.encode_batch(
        entries_to_translate=[entry],
        context_before=[],
        context_after=[],
        batch_num=1,
        total_batches=1
    )

    print(f"Encoded IBF:\n{encoded}")

    # Check newline is escaped
    if "\\n" not in encoded:
        print("FAIL: Newline in text not escaped to \\n")
        return False

    # Entry should be on single line (no actual newlines in entry)
    entry_line = [l for l in encoded.split('\n') if l.startswith('[1]')]
    if len(entry_line) != 1:
        print("FAIL: Entry spans multiple lines (newline not escaped)")
        return False

    # Simulate translated response with escaped newline
    translated_response = """#TRANSLATED:v1:batch=1/1:count=1:status=ok
[1] Birinci satir\\nIkinci satir
---"""

    metadata, decoded = decoder.decode(translated_response)

    if len(decoded) != 1:
        print(f"FAIL: Expected 1 entry, got {len(decoded)}")
        return False

    # Text should have real newline restored
    expected_text = "Birinci satir\nIkinci satir"
    if decoded[0].text != expected_text:
        print(f"FAIL: Expected text '{repr(expected_text)}', got '{repr(decoded[0].text)}'")
        return False

    print(f"Decoded text: {repr(decoded[0].text)}")
    print("PASS: Multiline text preserved after encode/decode")
    return True


def test_validation_accepts_empty_entries():
    """BUG 1: Test that validation does NOT flag empty entries as errors."""
    print("\n=== TEST 4: Validation Accepts Empty Entries ===")

    decoder = IBFDecoder()

    # Create decoded entries with empty text
    decoded_entries = [
        IBFEntry('1', ''),  # Empty translation
        IBFEntry('2', 'Valid text'),
    ]

    # Validate against original IDs
    original_ids = ['1', '2']
    is_valid, errors = decoder.validate(original_ids, decoded_entries)

    print(f"Is valid: {is_valid}")
    print(f"Errors: {errors}")

    if not is_valid:
        # Check if error is about empty translation
        for err in errors:
            if 'empty' in err.message.lower():
                print("FAIL: Validation incorrectly flagged empty translation as error")
                return False
        print(f"FAIL: Unexpected validation errors: {errors}")
        return False

    print("PASS: Validation accepts empty entries without errors")
    return True


def test_file_format_validation_with_empty():
    """BUG 1: Test validate_file_format accepts empty entries."""
    print("\n=== TEST 5: File Format Validation with Empty Entries ===")

    decoder = IBFDecoder()

    # File content with empty translation
    content = """#TRANSLATED:v1:batch=1/1:count=2:status=ok
[1]
[2] Some text
---"""

    is_valid, errors = decoder.validate_file_format(content)

    print(f"Is valid: {is_valid}")
    print(f"Errors: {[e.to_dict() for e in errors]}")

    if not is_valid:
        # Check if any error mentions empty
        for err in errors:
            if 'empty' in err.message.lower():
                print("FAIL: File validation incorrectly flagged empty entry")
                return False
        print(f"FAIL: Unexpected validation errors")
        return False

    print("PASS: File format validation accepts empty entries")
    return True


def test_full_round_trip():
    """Comprehensive round-trip test with complex data."""
    print("\n=== TEST 6: Full Round-Trip with Complex Data ===")

    encoder = IBFEncoder(context_size=2)
    decoder = IBFDecoder()

    # Complex entries with various edge cases
    entries_to_translate = [
        IBFEntry('msg.greeting', 'Hello\nWorld'),  # Multiline text
        IBFEntry('key\nwith\nnewlines', 'Simple text'),  # Multiline ID
        IBFEntry('empty.value', ''),  # Empty text
        IBFEntry('special', 'Tab\there and\tthere'),  # Tabs
    ]

    context_before = [
        IBFEntry('prev.1', 'Previous context'),
    ]

    context_after = [
        IBFEntry('next.1', 'Next context'),
    ]

    # Encode
    encoded = encoder.encode_batch(
        entries_to_translate=entries_to_translate,
        context_before=context_before,
        context_after=context_after,
        batch_num=2,
        total_batches=5
    )

    print(f"Encoded IBF:\n{encoded}")
    print()

    # Verify encoding properties
    lines = encoded.split('\n')

    # Check no entry line contains actual newline (all should be single-line)
    entry_lines = [l for l in lines if l.startswith('[')]
    for el in entry_lines:
        if '\n' in el[1:]:  # Skip first [ char
            print(f"FAIL: Entry has unescaped newline: {repr(el)}")
            return False

    # Check escaped newlines present
    if "\\n" not in encoded:
        print("FAIL: No escaped newlines found in output")
        return False

    # Simulate translated response maintaining structure
    translated_response = """#TRANSLATED:v1:batch=2/5:count=4:status=ok
[msg.greeting] Merhaba\\nDunya
[key\\nwith\\nnewlines] Basit metin
[empty.value]
[special] Sekme\\tburada ve\\torada
---"""

    metadata, decoded = decoder.decode(translated_response)

    print(f"Decoded {len(decoded)} entries:")
    for e in decoded:
        print(f"  ID: {repr(e.id)}, Text: {repr(e.text)}")

    # Verify count
    if len(decoded) != 4:
        print(f"FAIL: Expected 4 entries, got {len(decoded)}")
        return False

    # Verify multiline text restored
    if decoded[0].text != "Merhaba\nDunya":
        print(f"FAIL: Multiline text not restored: {repr(decoded[0].text)}")
        return False

    # Verify multiline ID restored
    if decoded[1].id != "key\nwith\nnewlines":
        print(f"FAIL: Multiline ID not restored: {repr(decoded[1].id)}")
        return False

    # Verify empty entry
    if decoded[2].text != "":
        print(f"FAIL: Empty text not preserved: {repr(decoded[2].text)}")
        return False

    # Verify metadata
    if metadata.batch_num != 2 or metadata.total_batches != 5:
        print(f"FAIL: Metadata incorrect: batch={metadata.batch_num}/{metadata.total_batches}")
        return False

    # Validate
    original_ids = [e.id for e in entries_to_translate]
    is_valid, errors = decoder.validate(original_ids, decoded, expected_batch=2, expected_total=5, metadata=metadata)

    print(f"Validation: valid={is_valid}, errors={errors}")

    if not is_valid:
        print(f"FAIL: Validation failed: {errors}")
        return False

    print("PASS: Full round-trip with complex data successful")
    return True


def test_entry_pattern_regex():
    """Directly test ENTRY_PATTERN regex for edge cases."""
    print("\n=== TEST 7: ENTRY_PATTERN Regex Direct Test ===")

    decoder = IBFDecoder()
    pattern = decoder.ENTRY_PATTERN

    test_cases = [
        ("[123] normal text", True, "123", "normal text"),
        ("[key.name] value", True, "key.name", "value"),
        ("[id] ", True, "id", ""),  # Empty text with trailing space
        ("[id]", True, "id", ""),  # Empty text no space (BUG 1)
        ("[id]  ", True, "id", ""),  # Empty text multiple spaces
        ("[complex.id.here] text", True, "complex.id.here", "text"),
        ("no brackets", False, None, None),
        ("[] empty id", False, None, None),  # Empty ID should fail
    ]

    all_passed = True
    for line, should_match, expected_id, expected_text in test_cases:
        match = pattern.match(line)
        matched = match is not None

        if matched != should_match:
            print(f"FAIL: Line '{line}' - expected match={should_match}, got {matched}")
            all_passed = False
            continue

        if matched and expected_id is not None:
            actual_id = match.group(1).strip()
            actual_text = match.group(2).strip()

            if actual_id != expected_id:
                print(f"FAIL: Line '{line}' - expected ID '{expected_id}', got '{actual_id}'")
                all_passed = False
            elif actual_text != expected_text:
                print(f"FAIL: Line '{line}' - expected text '{expected_text}', got '{actual_text}'")
                all_passed = False
            else:
                print(f"  OK: '{line}' -> ID='{actual_id}', text='{actual_text}'")

    if all_passed:
        print("PASS: All ENTRY_PATTERN regex tests passed")
    return all_passed


def main():
    """Run all tests."""
    print("=" * 60)
    print("IBF FORMAT BUG FIX VERIFICATION TESTS")
    print("=" * 60)

    tests = [
        test_empty_string_entry,
        test_multiline_id,
        test_multiline_text,
        test_validation_accepts_empty_entries,
        test_file_format_validation_with_empty,
        test_full_round_trip,
        test_entry_pattern_regex,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"FAIL: {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {name}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("\nALL TESTS PASSED - Bug fixes verified!")
        return 0
    else:
        print(f"\n{total - passed} TEST(S) FAILED - Check implementation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
