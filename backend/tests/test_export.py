from types import SimpleNamespace

from app.services.export import render_project_markdown


def _project(**kw):
    base = {"id": 1, "title": "Creativity Book", "description": "A study."}
    base.update(kw)
    return SimpleNamespace(**base)


def _node(**kw):
    base = {
        "id": kw.get("id", 1),
        "project_id": 1,
        "parent_id": None,
        "title": "Untitled",
        "kind": "section",
        "order_in_parent": 0,
        "body_md": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _evidence(**kw):
    base = {
        "id": kw.get("id", 1),
        "outline_node_id": 1,
        "source_id": 7,
        "chunk_id": 99,
        "quote_text": "Flow is total absorption.",
        "citation": {
            "source_title": "Flow",
            "chapter_path": ["Part I", "Chapter 1"],
            "page_start": 12,
            "page_end": 12,
        },
        "note": None,
        "order_in_node": 0,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _source(**kw):
    base = {
        "id": 7,
        "title": "Flow",
        "authors": ["Mihaly Csikszentmihalyi"],
        "year": 1990,
        "publisher": "Harper",
        "isbn": "9780060920432",
        "doi": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_render_emits_yaml_heading_and_body():
    n1 = _node(id=1, title="Introduction", body_md="<p>Hello world.</p>")
    md = render_project_markdown(_project(), [n1], [], {})
    assert md.startswith("---\n")
    assert "title: \"Creativity Book\"" in md
    assert "# Creativity Book" in md
    assert "## Introduction" in md
    assert "<p>Hello world.</p>" in md


def test_render_nests_children_with_increasing_heading_depth():
    parent = _node(id=1, title="Part One")
    child = _node(id=2, parent_id=1, title="Chapter One")
    grand = _node(id=3, parent_id=2, title="Section One")
    md = render_project_markdown(_project(), [parent, child, grand], [], {})
    assert "## Part One" in md
    assert "### Chapter One" in md
    assert "#### Section One" in md


def test_render_inserts_pandoc_citation_keys_and_bibliography():
    n = _node(id=1, title="Findings")
    e = _evidence()
    md = render_project_markdown(_project(), [n], [e], {7: _source()})
    assert "[@src7]" in md
    assert "Part I > Chapter 1" in md
    assert "p. 12" in md
    assert "# References" in md
    assert "**[@src7]**" in md
    assert "Flow" in md
    assert "Csikszentmihalyi" in md


def test_render_skips_bibliography_when_no_evidence():
    md = render_project_markdown(_project(), [_node(id=1)], [], {})
    assert "# References" not in md


def test_render_orders_evidence_within_node():
    n = _node(id=1)
    e1 = _evidence(id=10, order_in_node=1, quote_text="second")
    e2 = _evidence(id=11, order_in_node=0, quote_text="first")
    md = render_project_markdown(_project(), [n], [e1, e2], {7: _source()})
    assert md.index("first") < md.index("second")
