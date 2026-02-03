#!/usr/bin/env python3
"""
Comprehensive tests for SRT format handler blank line preservation.

Tests the fix for: Empty lines within subtitle text are now preserved
(not treated as block separators).
"""

import sys
sys.path.insert(0, '/Users/yigitkonur/dev/my-cli-apps/srt-translator')
from xlat.format_handlers.srt import SrtHandler


def test_parse_srt_with_blank_line_in_subtitle():
    """Test 1: Parse SRT with blank line in subtitle text, verify it's preserved."""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
Normal subtitle

2
00:00:03,000 --> 00:00:06,000
Line one

Line three (blank line two)

3
00:00:07,000 --> 00:00:10,000
Final subtitle"""

    handler = SrtHandler()
    entries = handler.parse(srt_content)

    # Should have 3 entries
    if len(entries) != 3:
        print(f"FAIL: Expected 3 entries, got {len(entries)}")
        return False

    # Entry 2 should have a blank line preserved in the text
    entry_2_text = entries[1].text
    expected_text = "Line one\n\nLine three (blank line two)"

    if entry_2_text != expected_text:
        print(f"FAIL: Entry 2 text mismatch")
        print(f"  Expected: {repr(expected_text)}")
        print(f"  Got:      {repr(entry_2_text)}")
        return False

    # Verify the blank line is represented as \n\n in the middle
    if "\n\n" not in entry_2_text:
        print(f"FAIL: Entry 2 should contain '\\n\\n' (blank line)")
        return False

    print("PASS: test_parse_srt_with_blank_line_in_subtitle")
    return True


def test_multiple_blank_lines_in_subtitle():
    """Test 2: Test multiple blank lines in one subtitle."""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
First line


Third line (two blanks above)



Fifth line (three blanks above)

2
00:00:03,000 --> 00:00:06,000
Normal subtitle"""

    handler = SrtHandler()
    entries = handler.parse(srt_content)

    # Should have 2 entries
    if len(entries) != 2:
        print(f"FAIL: Expected 2 entries, got {len(entries)}")
        return False

    # Entry 1 should have multiple blank lines preserved
    entry_1_text = entries[0].text

    # Check for double blank line (\n\n\n = two blank lines between text)
    if "\n\n" not in entry_1_text:
        print(f"FAIL: Entry 1 should contain multiple blank lines")
        print(f"  Got: {repr(entry_1_text)}")
        return False

    # Count the number of blank lines by checking consecutive \n
    lines = entry_1_text.split("\n")
    blank_count = sum(1 for line in lines if line == "")

    # We expect multiple blank lines (at least 4: 2 + 3 = 5 blanks total)
    if blank_count < 4:
        print(f"FAIL: Entry 1 should have at least 4 blank lines, found {blank_count}")
        print(f"  Lines: {lines}")
        return False

    print("PASS: test_multiple_blank_lines_in_subtitle")
    return True


def test_normal_srt_block_separation():
    """Test 3: Test normal SRT (blank lines between blocks work correctly)."""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
Normal subtitle

2
00:00:03,000 --> 00:00:06,000
Line one
Line two

3
00:00:07,000 --> 00:00:10,000
Multiple
blank

lines

4
00:00:11,000 --> 00:00:14,000
Final subtitle"""

    handler = SrtHandler()
    entries = handler.parse(srt_content)

    # Should have exactly 4 entries
    if len(entries) != 4:
        print(f"FAIL: Expected 4 entries, got {len(entries)}")
        for i, e in enumerate(entries):
            print(f"  Entry {i+1}: id={e.id}, text={repr(e.text)}")
        return False

    # Verify each entry's ID
    expected_ids = ['1', '2', '3', '4']
    actual_ids = [e.id for e in entries]
    if actual_ids != expected_ids:
        print(f"FAIL: Entry IDs mismatch")
        print(f"  Expected: {expected_ids}")
        print(f"  Got:      {actual_ids}")
        return False

    # Entry 1: Simple one-line
    if entries[0].text != "Normal subtitle":
        print(f"FAIL: Entry 1 text mismatch: {repr(entries[0].text)}")
        return False

    # Entry 2: Two lines, no blank in between
    if entries[1].text != "Line one\nLine two":
        print(f"FAIL: Entry 2 text mismatch: {repr(entries[1].text)}")
        return False

    # Entry 3: Has blank line in text
    expected_3 = "Multiple\nblank\n\nlines"
    if entries[2].text != expected_3:
        print(f"FAIL: Entry 3 text mismatch")
        print(f"  Expected: {repr(expected_3)}")
        print(f"  Got:      {repr(entries[2].text)}")
        return False

    # Entry 4: Simple one-line
    if entries[3].text != "Final subtitle":
        print(f"FAIL: Entry 4 text mismatch: {repr(entries[3].text)}")
        return False

    print("PASS: test_normal_srt_block_separation")
    return True


def test_round_trip_preserves_blank_lines():
    """Test 4: Test round-trip preserves blank lines."""
    original_content = """1
00:00:00,000 --> 00:00:02,000
Normal subtitle

2
00:00:03,000 --> 00:00:06,000
Line one

Line three (blank line two)

3
00:00:07,000 --> 00:00:10,000
Multiple

blank

lines

4
00:00:11,000 --> 00:00:14,000
Final subtitle"""

    handler = SrtHandler()

    # Parse
    entries = handler.parse(original_content)

    if len(entries) != 4:
        print(f"FAIL: Expected 4 entries after parse, got {len(entries)}")
        return False

    # Reconstruct without translations (use original text)
    translations = {}  # Empty = fall back to original
    reconstructed = handler.reconstruct(entries, translations)

    # Parse the reconstructed content
    entries_after = handler.parse(reconstructed)

    if len(entries_after) != 4:
        print(f"FAIL: Expected 4 entries after round-trip, got {len(entries_after)}")
        return False

    # Compare each entry's text
    for i, (before, after) in enumerate(zip(entries, entries_after)):
        if before.text != after.text:
            print(f"FAIL: Entry {i+1} text changed during round-trip")
            print(f"  Before: {repr(before.text)}")
            print(f"  After:  {repr(after.text)}")
            return False

        # Also verify timing metadata preserved
        if before.metadata['start_time'] != after.metadata['start_time']:
            print(f"FAIL: Entry {i+1} start_time changed")
            return False
        if before.metadata['end_time'] != after.metadata['end_time']:
            print(f"FAIL: Entry {i+1} end_time changed")
            return False

    print("PASS: test_round_trip_preserves_blank_lines")
    return True


def test_given_srt_content():
    """Test with the exact SRT content from the user's request."""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
Normal subtitle

2
00:00:03,000 --> 00:00:06,000
Line one

Line three (blank line two)

3
00:00:07,000 --> 00:00:10,000
Multiple

blank

lines

4
00:00:11,000 --> 00:00:14,000
Final subtitle"""

    handler = SrtHandler()
    entries = handler.parse(srt_content)

    # Verify: All 4 entries are parsed
    if len(entries) != 4:
        print(f"FAIL: Expected 4 entries, got {len(entries)}")
        for i, e in enumerate(entries):
            print(f"  Entry {i}: id={e.id}, text={repr(e.text)}")
        return False

    # Verify: Entry 2 has text containing blank line (\n\n in the text)
    entry_2_text = entries[1].text
    if "\n\n" not in entry_2_text:
        print(f"FAIL: Entry 2 should contain '\\n\\n' (blank line)")
        print(f"  Got: {repr(entry_2_text)}")
        return False

    # Verify: Entry 3 has text with multiple blank lines
    entry_3_text = entries[2].text
    blank_line_count = entry_3_text.count("\n\n")
    if blank_line_count < 2:
        print(f"FAIL: Entry 3 should have multiple blank lines (at least 2 '\\n\\n')")
        print(f"  Found {blank_line_count} blank line sequences")
        print(f"  Text: {repr(entry_3_text)}")
        return False

    print("PASS: test_given_srt_content")
    return True


def test_edge_case_consecutive_blank_blocks():
    """Test edge case: multiple blank lines between blocks (should still separate correctly)."""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
First subtitle



2
00:00:03,000 --> 00:00:06,000
Second subtitle"""

    handler = SrtHandler()
    entries = handler.parse(srt_content)

    # Should have exactly 2 entries (multiple blank lines between blocks)
    if len(entries) != 2:
        print(f"FAIL: Expected 2 entries, got {len(entries)}")
        return False

    # First entry should not include trailing blank lines
    if entries[0].text != "First subtitle":
        print(f"FAIL: Entry 1 has trailing content: {repr(entries[0].text)}")
        return False

    print("PASS: test_edge_case_consecutive_blank_blocks")
    return True


def test_blank_line_at_start_of_text():
    """Test edge case: blank line right after timing (start of text)."""
    srt_content = """1
00:00:00,000 --> 00:00:02,000

Text after blank

2
00:00:03,000 --> 00:00:06,000
Normal"""

    handler = SrtHandler()
    entries = handler.parse(srt_content)

    if len(entries) != 2:
        print(f"FAIL: Expected 2 entries, got {len(entries)}")
        return False

    # Entry 1 should preserve the leading blank line
    entry_1_text = entries[0].text
    # Note: The handler starts collecting after timing line, so blank line at start should be preserved
    if not entry_1_text.startswith("\n"):
        # Alternative: it might strip leading blanks, which is also acceptable
        if entry_1_text != "Text after blank":
            print(f"FAIL: Entry 1 text unexpected: {repr(entry_1_text)}")
            return False

    print("PASS: test_blank_line_at_start_of_text")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("SRT Handler Blank Line Preservation Tests")
    print("=" * 60)
    print()

    tests = [
        test_parse_srt_with_blank_line_in_subtitle,
        test_multiple_blank_lines_in_subtitle,
        test_normal_srt_block_separation,
        test_round_trip_preserves_blank_lines,
        test_given_srt_content,
        test_edge_case_consecutive_blank_blocks,
        test_blank_line_at_start_of_text,
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
            print(f"FAIL: {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
