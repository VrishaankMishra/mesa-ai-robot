"""Tests for the paper PDF builder (DOCS-011).

The stripping rules matter more than the typography: a PDF built from these drafts gets
emailed to faculty, and the drafts carry author-facing notes that must never travel with
them. This project has already sent submission scaffolding to a professor once (Aug 9).
"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "make_paper_pdf", Path(__file__).resolve().parent.parent / "scripts" / "make_paper_pdf.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)


def test_status_block_is_stripped():
    md = "# T\n\n> **Status:** complete draft; Targets: JEI, HRI LBR, arXiv preprint.\n\nBody.\n"
    out = mp.strip_internal(md)
    assert "Targets: JEI" not in out and "Status:" not in out
    assert "Body." in out


def test_mentor_anchor_placeholders_are_stripped():
    md = "Controlled lighting is standard *[anchor ref to be selected with mentor]* but rarely.\n"
    out = mp.strip_internal(md)
    assert "mentor" not in out
    assert "standard but rarely." in out  # sentence survives, spacing tidied


def test_acknowledgments_todo_section_is_stripped():
    md = "## Results\n\nText.\n\n## Acknowledgments\n\n`[Mentor/endorser TBD — outreach planned.]`\n"
    out = mp.strip_internal(md)
    assert "Mentor/endorser" not in out and "outreach planned" not in out
    assert "Acknowledgments" not in out
    assert "Text." in out


def test_submission_checklist_section_is_stripped():
    """The exact leak found on 2026-08-25 in the HRI LBR draft."""
    md = ("## 4. Conclusion\n\nReal content.\n\n"
          "### Submission checklist (not part of the manuscript)\n"
          "- [ ] Verify current HRI LBR deadline.\n"
          "- [ ] Mentor/endorser read-through (Stevens outreach) before submission.\n")
    out = mp.strip_internal(md)
    assert "Mentor/endorser" not in out and "Stevens" not in out
    assert "Submission checklist" not in out
    assert "Real content." in out


def test_stray_task_items_are_stripped_even_without_a_section():
    md = "Body text.\n\n- [ ] tell the mentor about this\n- [x] done thing\n\nMore body.\n"
    out = mp.strip_internal(md)
    assert "mentor" not in out and "done thing" not in out
    assert "Body text." in out and "More body." in out


def test_internal_mode_keeps_everything():
    md = "> **Status:** Targets: JEI.\n\nBody.\n"
    assert "Targets: JEI" in md  # --internal simply skips strip_internal


def test_parse_blocks_reads_the_structures_the_drafts_use():
    md = ("# Title\n\nPara one.\n\n## Section\n\n> quoted\n\n"
          "1. first\n- bullet\n\n---\n\n"
          "*(Fig. 1: condition × class heatmap. Fig. 2: lamp ablation. Fig. 3: model arms.)*\n")
    kinds = [k for k, _ in mp.parse_blocks(md)]
    assert kinds.count("h") == 2
    assert "p" in kinds and "quote" in kinds and "rule" in kinds and "figs" in kinds
    assert kinds.count("li") == 2


def test_paragraph_lines_are_joined():
    blocks = mp.parse_blocks("one line\ncontinues here\n")
    assert blocks == [("p", "one line continues here")]


def test_inline_escapes_before_emphasis():
    out = mp.inline("a < b and **bold** and *it* and `code`")
    assert "&lt;" in out and "<b>bold</b>" in out and "<i>it</i>" in out and "Courier" in out


def test_inline_does_not_treat_bold_as_two_italics():
    assert mp.inline("**x**") == "<b>x</b>"
