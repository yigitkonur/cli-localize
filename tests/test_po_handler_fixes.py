#!/usr/bin/env python3
"""
Comprehensive tests for PO format handler fixes:
1. Header metadata preservation (Plural-Forms, Project-Id-Version)
2. Long string wrapping at ~76 characters using continuation format
"""

import sys
sys.path.insert(0, '/Users/yigitkonur/dev/my-cli-apps/srt-translator')

from xlat.format_handlers.po import PoHandler


def test_header_metadata_stored():
    """Test 1: Parse PO file with full header, verify _header_metadata is stored."""
    po_content = '''msgid ""
msgstr ""
"Project-Id-Version: TestProject 1.0\\n"
"Plural-Forms: nplurals=2; plural=n != 1;\\n"
"Language: tr\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Merhaba"
'''

    handler = PoHandler()
    entries = handler.parse(po_content)

    # Check that header metadata was stored
    has_metadata = bool(handler._header_metadata)
    has_plural_forms = 'Plural-Forms' in handler._header_metadata if has_metadata else False
    has_project_id = 'Project-Id-Version' in handler._header_metadata if has_metadata else False

    if has_metadata and has_plural_forms and has_project_id:
        print("PASS: test_header_metadata_stored - _header_metadata contains Plural-Forms and Project-Id-Version")
    else:
        print(f"FAIL: test_header_metadata_stored")
        print(f"  - _header_metadata stored: {has_metadata}")
        print(f"  - Contains Plural-Forms: {has_plural_forms}")
        print(f"  - Contains Project-Id-Version: {has_project_id}")
        if has_metadata:
            print(f"  - Actual content: {repr(handler._header_metadata)}")

    return has_metadata and has_plural_forms and has_project_id


def test_header_restored_on_reconstruct():
    """Test 2: Reconstruct and verify header is restored (not hardcoded minimal)."""
    po_content = '''msgid ""
msgstr ""
"Project-Id-Version: TestProject 1.0\\n"
"Plural-Forms: nplurals=2; plural=n != 1;\\n"
"Language: tr\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Merhaba"
'''

    handler = PoHandler()
    entries = handler.parse(po_content)

    # Reconstruct with no translations (keep original)
    translations = {"Hello": "Merhaba"}
    result = handler.reconstruct(entries, translations)

    # Verify header contains original metadata
    has_project_id = 'Project-Id-Version: TestProject 1.0' in result
    has_language = 'Language: tr' in result

    if has_project_id and has_language:
        print("PASS: test_header_restored_on_reconstruct - Header restored with Project-Id-Version and Language")
    else:
        print(f"FAIL: test_header_restored_on_reconstruct")
        print(f"  - Contains Project-Id-Version: {has_project_id}")
        print(f"  - Contains Language: {has_language}")
        print(f"  - Reconstructed output:\n{result[:500]}")

    return has_project_id and has_language


def test_plural_forms_survives_roundtrip():
    """Test 3: Test Plural-Forms header survives round-trip."""
    po_content = '''msgid ""
msgstr ""
"Project-Id-Version: TestProject 1.0\\n"
"Plural-Forms: nplurals=2; plural=n != 1;\\n"
"Language: tr\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Merhaba"

msgid "World"
msgstr "Dunya"
'''

    handler = PoHandler()
    entries = handler.parse(po_content)

    # Simulate translation
    translations = {
        "Hello": "Selam",
        "World": "Dunya"
    }

    result = handler.reconstruct(entries, translations)

    # Check that Plural-Forms appears in reconstructed output
    has_plural_forms = 'Plural-Forms:' in result
    has_nplurals = 'nplurals=2' in result

    if has_plural_forms and has_nplurals:
        print("PASS: test_plural_forms_survives_roundtrip - Plural-Forms: nplurals=2 found in output")
    else:
        print(f"FAIL: test_plural_forms_survives_roundtrip")
        print(f"  - Contains 'Plural-Forms:': {has_plural_forms}")
        print(f"  - Contains 'nplurals=2': {has_nplurals}")
        # Show header portion of output
        header_end = result.find('msgid "Hello"')
        if header_end > 0:
            print(f"  - Header portion:\n{result[:header_end]}")

    return has_plural_forms and has_nplurals


def test_long_string_wrapping():
    """Test 4: Test long string wrapping (strings >76 chars should use continuation format)."""
    long_msgid = "This is a very long string that should be wrapped at approximately 76 characters to maintain proper PO file formatting and readability"

    po_content = f'''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "{long_msgid}"
msgstr ""
'''

    handler = PoHandler()
    entries = handler.parse(po_content)

    # Translate with a long string
    long_translation = "Bu, PO dosya biçimlendirmesini ve okunabilirliğini korumak için yaklaşık 76 karakterde sarılması gereken çok uzun bir dizedir"
    translations = {long_msgid: long_translation}

    result = handler.reconstruct(entries, translations)

    # Check for continuation format in msgid (should have msgid "" followed by quoted lines)
    # Long strings should be split with msgid "" on first line, then continuation lines
    lines = result.split('\n')

    # Find the msgid line for our long string
    found_continuation = False
    for i, line in enumerate(lines):
        # Skip the header msgid ""
        if line == 'msgid ""' and i > 0:
            # Check if next line is a continuation (starts with ")
            if i + 1 < len(lines) and lines[i + 1].startswith('"'):
                found_continuation = True
                break

    # Also verify no single line exceeds ~80 characters (allowing some margin)
    max_line_length = max(len(line) for line in lines)
    lines_under_limit = max_line_length <= 85  # Allow small margin

    if found_continuation and lines_under_limit:
        print(f"PASS: test_long_string_wrapping - Found continuation format, max line length: {max_line_length}")
    else:
        print(f"FAIL: test_long_string_wrapping")
        print(f"  - Found continuation format: {found_continuation}")
        print(f"  - All lines under ~80 chars: {lines_under_limit} (max: {max_line_length})")
        # Show the problematic msgid section
        for i, line in enumerate(lines):
            if 'very long string' in line or line.startswith('msgid'):
                print(f"  - Line {i}: {line[:100]}...")

    return found_continuation and lines_under_limit


def test_format_po_string_directly():
    """Test 5: Test _format_po_string method directly for proper wrapping."""
    handler = PoHandler()

    # Test short string (should be single line)
    short_result = handler._format_po_string('msgid', 'Hello world')
    short_ok = len(short_result) == 1 and short_result[0] == 'msgid "Hello world"'

    # Test long string (should be multi-line)
    long_string = "This is a very long string that absolutely needs to be wrapped because it exceeds the 76 character limit for PO files"
    long_result = handler._format_po_string('msgid', long_string)
    long_ok = len(long_result) > 1 and long_result[0] == 'msgid ""'

    # Check all continuation lines start with "
    continuation_ok = all(line.startswith('"') for line in long_result[1:]) if len(long_result) > 1 else False

    if short_ok and long_ok and continuation_ok:
        print(f"PASS: test_format_po_string_directly - Short={len(short_result)} lines, Long={len(long_result)} lines")
    else:
        print(f"FAIL: test_format_po_string_directly")
        print(f"  - Short string single line: {short_ok}")
        print(f"  - Long string multi-line: {long_ok}")
        print(f"  - Continuation format correct: {continuation_ok}")
        print(f"  - Short result: {short_result}")
        print(f"  - Long result: {long_result}")

    return short_ok and long_ok and continuation_ok


def test_string_with_newlines_wrapping():
    """Test 6: Test that strings with \\n are properly split and wrapped."""
    handler = PoHandler()

    # String with embedded newlines
    string_with_newlines = "First line of text\nSecond line that is quite long and might need additional wrapping\nThird line"
    result = handler._format_po_string('msgstr', string_with_newlines)

    # Should be multi-line format
    is_multiline = len(result) > 1 and result[0] == 'msgstr ""'

    # Check that \\n appears in the output (escaped form)
    has_escaped_newlines = any('\\n' in line for line in result)

    if is_multiline and has_escaped_newlines:
        print(f"PASS: test_string_with_newlines_wrapping - Multi-line with escaped \\n, {len(result)} lines")
    else:
        print(f"FAIL: test_string_with_newlines_wrapping")
        print(f"  - Is multi-line: {is_multiline}")
        print(f"  - Has escaped newlines: {has_escaped_newlines}")
        print(f"  - Result: {result}")

    return is_multiline and has_escaped_newlines


def test_header_comments_preserved():
    """Test 7: Test that header comments are preserved."""
    po_content = '''# Translation file for TestProject
# Generated by test suite
msgid ""
msgstr ""
"Project-Id-Version: TestProject 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Test"
msgstr "Test"
'''

    handler = PoHandler()
    entries = handler.parse(po_content)

    # Check header comments stored
    comments_stored = len(handler._header_comments) > 0
    has_translation_comment = any('Translation file' in c for c in handler._header_comments) if comments_stored else False

    # Reconstruct and check comments appear
    result = handler.reconstruct(entries, {"Test": "Test"})
    comments_in_output = '# Translation file for TestProject' in result

    if comments_stored and has_translation_comment and comments_in_output:
        print(f"PASS: test_header_comments_preserved - {len(handler._header_comments)} comments stored and restored")
    else:
        print(f"FAIL: test_header_comments_preserved")
        print(f"  - Comments stored: {comments_stored}")
        print(f"  - Has 'Translation file' comment: {has_translation_comment}")
        print(f"  - Comments in output: {comments_in_output}")
        print(f"  - Stored comments: {handler._header_comments}")

    return comments_stored and has_translation_comment and comments_in_output


def test_empty_header_fallback():
    """Test 8: Test fallback to minimal header when no header metadata exists."""
    # PO file without proper header
    po_content = '''msgid "Hello"
msgstr "Hola"
'''

    handler = PoHandler()
    entries = handler.parse(po_content)

    result = handler.reconstruct(entries, {"Hello": "Hola"})

    # Should have minimal header with Content-Type
    has_header_msgid = 'msgid ""' in result
    has_content_type = 'Content-Type: text/plain; charset=UTF-8' in result

    if has_header_msgid and has_content_type:
        print("PASS: test_empty_header_fallback - Minimal header with Content-Type added")
    else:
        print(f"FAIL: test_empty_header_fallback")
        print(f"  - Has header msgid: {has_header_msgid}")
        print(f"  - Has Content-Type: {has_content_type}")
        print(f"  - Output start: {result[:200]}")

    return has_header_msgid and has_content_type


def run_all_tests():
    """Run all tests and report summary."""
    print("=" * 60)
    print("Testing PO Format Handler Fixes")
    print("=" * 60)
    print()

    tests = [
        ("1. Header metadata stored on parse", test_header_metadata_stored),
        ("2. Header restored on reconstruct", test_header_restored_on_reconstruct),
        ("3. Plural-Forms survives round-trip", test_plural_forms_survives_roundtrip),
        ("4. Long string wrapping", test_long_string_wrapping),
        ("5. _format_po_string direct test", test_format_po_string_directly),
        ("6. String with newlines wrapping", test_string_with_newlines_wrapping),
        ("7. Header comments preserved", test_header_comments_preserved),
        ("8. Empty header fallback", test_empty_header_fallback),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"ERROR: {name} raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests PASSED!")
        return 0
    else:
        print(f"\n{total - passed} test(s) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
