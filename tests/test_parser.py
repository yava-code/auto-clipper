import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.parser import parse, transform


class TestLines:
    def test_basic(self):
        assert parse("a\nb\nc", "lines") == ["a", "b", "c"]

    def test_strips_whitespace(self):
        assert parse("  a  \n  b  ", "lines") == ["a", "b"]

    def test_skips_blank_lines(self):
        assert parse("a\n\n\nb", "lines") == ["a", "b"]

    def test_empty(self):
        assert parse("", "lines") == []


class TestComma:
    def test_basic(self):
        assert parse("a,b,c", "comma") == ["a", "b", "c"]

    def test_strips(self):
        assert parse(" a , b , c ", "comma") == ["a", "b", "c"]

    def test_skips_empty(self):
        assert parse("a,,b", "comma") == ["a", "b"]


class TestSentences:
    def test_period(self):
        result = parse("Hello. World.", "sentences")
        assert result == ["Hello.", "World."]

    def test_mixed(self):
        result = parse("Yes! No? Maybe.", "sentences")
        assert "Yes!" in result
        assert "No?" in result


class TestCustom:
    def test_delimiter(self):
        assert parse("a;b;c", "custom", delimiter=";") == ["a", "b", "c"]

    def test_regex_split(self):
        result = parse("a1b2c", "custom",
                       custom_mode="regex_split", regex_pattern=r"\d")
        assert result == ["a", "b", "c"]

    def test_regex_findall(self):
        result = parse("abc 123 def 456", "custom",
                       custom_mode="regex_findall", regex_pattern=r"\d+")
        assert result == ["123", "456"]

    def test_unknown_mode_falls_back_to_delimiter(self):
        result = parse("a;b", "custom", delimiter=";", custom_mode="delimiter")
        assert result == ["a", "b"]


class TestTransform:
    def test_prefix(self):
        assert transform(["a", "b"], prefix=">>") == [">>a", ">>b"]

    def test_suffix(self):
        assert transform(["a", "b"], suffix="<<") == ["a<<", "b<<"]

    def test_both(self):
        assert transform(["x"], prefix='"', suffix='"') == ['"x"']

    def test_empty(self):
        assert transform(["a"], prefix="", suffix="") == ["a"]
