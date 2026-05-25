from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.core.font_catalog import (
    _CAMEL_TO_SPACE_RE,
    _project_font_family_name,
    build_font_catalog,
    build_project_fonts_stylesheet,
    list_project_font_entries,
)


class ProjectFontFamilyNameTests(unittest.TestCase):
    def test_dashes_and_underscores_become_spaces(self) -> None:
        self.assertEqual(_project_font_family_name(Path("Roboto-Regular.ttf")), "Roboto Regular")
        self.assertEqual(_project_font_family_name(Path("noto_sans_jp.otf")), "noto sans jp")

    def test_camelcase_is_split_for_bundled_fonts(self) -> None:
        # Filenames coming straight from Google Fonts ZIPs use PascalCase
        # without separators, so the dropdown label and the @font-face
        # declaration must agree on the human-readable rendering.
        self.assertEqual(_project_font_family_name(Path("OpenSans-Regular.ttf")), "Open Sans Regular")
        self.assertEqual(_project_font_family_name(Path("JetBrainsMono-Bold.ttf")), "Jet Brains Mono Bold")
        self.assertEqual(_project_font_family_name(Path("PlayfairDisplay-Regular.ttf")), "Playfair Display Regular")

    def test_digit_boundaries_are_split(self) -> None:
        self.assertEqual(_project_font_family_name(Path("SourceSans3-Bold.ttf")), "Source Sans 3 Bold")

    def test_acronym_with_version_digits_stays_intact(self) -> None:
        """Themed fonts like `VT323` and `C64` are single tokens — the
        upstream Google Fonts family is literally `VT323`. The CamelCase
        splitter must not insert a space between an uppercase acronym and
        an immediately following digit run."""
        self.assertEqual(_project_font_family_name(Path("VT323-Regular.ttf")), "VT323 Regular")
        self.assertEqual(_project_font_family_name(Path("C64-Regular.ttf")), "C64 Regular")
        self.assertEqual(_project_font_family_name(Path("HK24-Bold.ttf")), "HK24 Bold")

    def test_acronym_then_titlecase_word_is_split(self) -> None:
        """When an acronym is followed by a TitleCase word — like the slug
        the Google Fonts CSS v1 API produces for "PT Mono" (`PTMono`) — the
        splitter must restore the original family name `PT Mono`, not
        leave it as `PTMono`."""
        self.assertEqual(_project_font_family_name(Path("PTMono-Regular.ttf")), "PT Mono Regular")
        self.assertEqual(_project_font_family_name(Path("PTSerif-Bold.ttf")), "PT Serif Bold")

    def test_camel_to_space_regex_is_idempotent(self) -> None:
        already_spaced = "Open Sans Regular"
        self.assertEqual(_CAMEL_TO_SPACE_RE.sub(" ", already_spaced), already_spaced)


class FontCatalogIntegrationTests(unittest.TestCase):
    def test_catalog_and_stylesheet_share_label_as_family(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            (tmp / "JetBrainsMono-Bold.ttf").write_bytes(b"fake-ttf-bytes")
            entries = list_project_font_entries(tmp)
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry["label"], "Jet Brains Mono Bold")
            self.assertEqual(entry["family"], '"Jet Brains Mono Bold"')
            self.assertEqual(entry["format"], "truetype")
            stylesheet = build_project_fonts_stylesheet(tmp)
            self.assertIn('font-family: "Jet Brains Mono Bold"', stylesheet)
            self.assertIn("/project-fonts/JetBrainsMono-Bold.ttf", stylesheet)

    def test_catalog_includes_project_and_fallback_sources(self) -> None:
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            (tmp / "Inter-Regular.ttf").write_bytes(b"fake")
            catalog = build_font_catalog(tmp)
            self.assertIn("project_local", catalog)
            self.assertIn("fallback", catalog)
            labels = [item["label"] for item in catalog["project_local"]]
            self.assertEqual(labels, ["Inter Regular"])


if __name__ == "__main__":
    unittest.main()
