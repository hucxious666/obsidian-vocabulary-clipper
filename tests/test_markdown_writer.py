import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clipper import markdown_writer
from clipper.markdown_writer import (
    DuplicateEntry,
    insert_chapter_entry,
    insert_news_entry,
    write_entry_atomic,
)


class SectionModelTests(unittest.TestCase):
    def test_discovers_h2_and_legacy_chapters_outside_code_fences(self):
        source = (
            "## 阅读笔记\n\n```md\n## 不应识别\n```\n\n"
            "**chapter 22**\n\n### chapter 23\n"
        )

        find_sections = getattr(markdown_writer, "find_sections", lambda _source: [])

        self.assertEqual(["阅读笔记", "Chapter 22", "Chapter 23"], find_sections(source))

    def test_inserts_entry_inside_named_section_before_next_h2(self):
        source = "## 足球\n\n1. goal /g/: <span class=\"meaning\">进球</span>\n\n## 新闻\n"
        insert_section_entry = getattr(
            markdown_writer,
            "insert_section_entry",
            lambda text, *_args: (text, 0),
        )

        updated, number = insert_section_entry(source, "足球", "player", "pleɪə", "球员")

        self.assertEqual(2, number)
        football, news = updated.split("## 新闻", 1)
        self.assertIn('2. player /pleɪə/: <span class="meaning">球员</span>', football)
        self.assertNotIn("player", news)

    def test_creates_normalized_h2_at_note_end(self):
        create_section = getattr(
            markdown_writer,
            "create_section",
            lambda text, _name: (text, ""),
        )

        updated, name = create_section("# 词汇\n", "  Match   Review  ")

        self.assertEqual("Match Review", name)
        self.assertTrue(updated.endswith("\n## Match Review\n"))

    def test_rejects_duplicate_section_name_case_insensitively(self):
        create_section = getattr(
            markdown_writer,
            "create_section",
            lambda text, _name: (text + "\n## football\n", "football"),
        )

        with self.assertRaises(ValueError):
            create_section("## Football\n", " football ")


class ChapterInsertionTests(unittest.TestCase):
    def test_recognizes_existing_heading_variants_and_inserts_before_separator(self):
        source = (
            "### chapter 1\n\n1. alpha /a/: <span class=\"meaning\">甲</span>\n\n"
            "---\n** chapter 2**\n\n1. beta /b/: <span class=\"meaning\">乙</span>\n"
        )
        updated, number = insert_chapter_entry(
            source, 1, "gamma", "g", "伽马"
        )
        self.assertEqual(2, number)
        self.assertIn(
            "2. gamma /g/: <span class=\"meaning\">伽马</span>\n\n---",
            updated,
        )

    def test_empty_last_chapter_starts_at_one(self):
        source = "**chapter 21**\n\n1. old /o/: <span class=\"meaning\">旧</span>\n\n---\n**chapter 22**\n\n"
        updated, number = insert_chapter_entry(source, 22, "new", "nu", "新的")
        self.assertEqual(1, number)
        self.assertTrue(updated.rstrip().endswith('1. new /nu/: <span class="meaning">新的</span>'))

    def test_duplicate_is_limited_to_selected_chapter(self):
        source = (
            "**chapter 1**\n\n1. repeat /r/: <span class=\"meaning\">重复</span>\n\n---\n"
            "**chapter 2**\n\n"
        )
        updated, number = insert_chapter_entry(source, 2, "repeat", "r", "重复")
        self.assertEqual(1, number)
        self.assertIn('1. repeat /r/: <span class="meaning">重复</span>', updated.split("**chapter 2**", 1)[1])

    def test_duplicate_in_same_chapter_is_rejected_case_insensitively(self):
        source = "**chapter 1**\n\n1. Repeat /r/: <span class=\"meaning\">重复</span>\n"
        with self.assertRaises(DuplicateEntry):
            insert_chapter_entry(source, 1, "repeat", "r", "重复")


class NewsInsertionTests(unittest.TestCase):
    def test_continues_tail_section_numbering(self):
        source = "*old*\n\n90. legacy /l/: <span class=\"meaning\">旧</span>\n\n*continue*\n\n33. last /l/: <span class=\"meaning\">最后</span>\n"
        updated, number = insert_news_entry(source, "next", "n", "下一个")
        self.assertEqual(34, number)
        self.assertTrue(updated.rstrip().endswith('34. next /n/: <span class="meaning">下一个</span>'))

    def test_news_duplicate_is_checked_across_file(self):
        source = "*old*\n\n1. Repeat /r/: <span class=\"meaning\">重复</span>\n\n*continue*\n\n"
        with self.assertRaises(DuplicateEntry):
            insert_news_entry(source, "repeat", "r", "重复")

    def test_escapes_translation_html(self):
        updated, _ = insert_news_entry("", "safe", "seɪf", "A < B & C > D")
        self.assertIn("A &lt; B &amp; C &gt; D", updated)

    def test_plain_style_writes_escaped_meaning_without_css_wrapper(self):
        updated, _ = insert_news_entry(
            "", "safe", "seɪf", "A < B & C > D", meaning_style="plain"
        )

        self.assertEqual("1. safe /seɪf/: A &lt; B &amp; C &gt; D\n", updated)
        self.assertNotIn('<span class="meaning">', updated)


class AtomicWriteTests(unittest.TestCase):
    def test_preserves_utf8_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "words.md"
            path.write_bytes(b"\xef\xbb\xbf**chapter 1**\r\n\r\n")

            result = write_entry_atomic(path, "chapter", 1, "word", "w", "词", Path(temp_dir) / "backups")

            data = path.read_bytes()
            self.assertEqual(1, result.number)
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", data)
            self.assertNotIn(b"\r\r\n", data)
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))

    def test_retries_when_file_changes_after_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "words.md"
            path.write_text("**chapter 1**\n\n", encoding="utf-8")
            calls = 0

            def mutate_once(_path, _backup_root):
                nonlocal calls
                calls += 1
                if calls == 1:
                    _path.write_text(_path.read_text(encoding="utf-8") + "external edit\n", encoding="utf-8")

            with patch("clipper.markdown_writer._backup_file", side_effect=mutate_once):
                write_entry_atomic(path, "chapter", 1, "word", "w", "词", Path(temp_dir) / "backups")

            result = path.read_text(encoding="utf-8")
            self.assertIn("external edit", result)
            self.assertIn("1. word /w/", result)
            self.assertEqual(2, calls)


if __name__ == "__main__":
    unittest.main()
