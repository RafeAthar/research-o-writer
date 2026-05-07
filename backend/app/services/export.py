"""Project → Markdown / DOCX export.

Output format choices:
- One Pandoc-friendly Markdown document per project.
- Inline citations use Pandoc citeproc keys: ``[@srcN]`` where N is the
  source_id.
- A trailing ``# References`` section enumerates each cited source in plain
  Markdown so the file is also useful with no toolchain.
- TipTap stores body content as HTML. Pandoc reads inline HTML inside Markdown
  fine; we emit it as a raw block instead of attempting a lossy HTML→MD pass.
- DOCX is produced by piping the same Markdown plus a CSL-JSON bibliography
  through ``pandoc --citeproc --csl=...``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.project import EvidenceCard, OutlineNode, Project
    from app.models.source import Source

CSL_DIR = Path(__file__).parent / "csl"
CSL_STYLES = {
    "chicago": CSL_DIR / "chicago-author-date.csl",
    "apa": CSL_DIR / "apa.csl",
}


@dataclass
class _Node:
    row: OutlineNode
    children: list["_Node"]
    evidence: list[EvidenceCard]


def _build_tree(nodes: Iterable[OutlineNode], evidence: Iterable[EvidenceCard]) -> list[_Node]:
    by_id: dict[int, _Node] = {n.id: _Node(row=n, children=[], evidence=[]) for n in nodes}
    for ec in evidence:
        if ec.outline_node_id in by_id:
            by_id[ec.outline_node_id].evidence.append(ec)
    roots: list[_Node] = []
    for node in by_id.values():
        if node.row.parent_id and node.row.parent_id in by_id:
            by_id[node.row.parent_id].children.append(node)
        else:
            roots.append(node)

    def _sort(group: list[_Node]) -> None:
        group.sort(key=lambda x: (x.row.order_in_parent, x.row.id))
        for child in group:
            _sort(child.children)
            child.evidence.sort(key=lambda e: (e.order_in_node, e.id))

    _sort(roots)
    return roots


def _cite_key(source_id: int) -> str:
    return f"src{source_id}"


def _format_authors(authors: list[str]) -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return f"{authors[0]} et al."


def _bibliography_entry(src: Source) -> str:
    parts: list[str] = []
    authors = _format_authors(list(src.authors or []))
    if authors:
        parts.append(authors)
    if src.year:
        parts.append(f"({src.year})")
    parts.append(f"*{src.title}*")
    if src.publisher:
        parts.append(src.publisher)
    if src.doi:
        parts.append(f"doi:{src.doi}")
    elif src.isbn:
        parts.append(f"ISBN {src.isbn}")
    return ". ".join(p.strip().rstrip(".") for p in parts if p) + "."


def _render_evidence(ec: EvidenceCard) -> str:
    cite = ec.citation or {}
    chap = " > ".join(cite.get("chapter_path") or [])
    page_start = cite.get("page_start")
    page_end = cite.get("page_end")
    page_str = ""
    if page_start and page_end and page_end != page_start:
        page_str = f"pp. {page_start}-{page_end}"
    elif page_start:
        page_str = f"p. {page_start}"
    locator_bits = [b for b in (chap, page_str) if b]
    locator = f" ({'; '.join(locator_bits)})" if locator_bits else ""
    quote = ec.quote_text.strip().replace("\n", "\n> ")
    body = f"> {quote}\n>\n> — [@{_cite_key(ec.source_id)}]{locator}"
    if ec.note:
        body += f"\n\n*Note: {ec.note.strip()}*"
    return body


def _render_node(node: _Node, depth: int) -> list[str]:
    heading_level = min(2 + depth, 6)
    out: list[str] = ["", f"{'#' * heading_level} {node.row.title}", ""]
    if node.row.body_md:
        # TipTap HTML lives inline in MD. Pandoc accepts this.
        out.extend([node.row.body_md.strip(), ""])
    if node.evidence:
        out.append("")
        for ec in node.evidence:
            out.extend([_render_evidence(ec), ""])
    for child in node.children:
        out.extend(_render_node(child, depth + 1))
    return out


def render_project_markdown(
    project: Project,
    nodes: list[OutlineNode],
    evidence: list[EvidenceCard],
    sources_by_id: dict[int, Source],
) -> str:
    tree = _build_tree(nodes, evidence)
    cited_ids = sorted({ec.source_id for ec in evidence if ec.source_id in sources_by_id})

    lines: list[str] = [
        "---",
        f"title: \"{project.title}\"",
        "link-citations: true",
        "---",
        "",
        f"# {project.title}",
    ]
    if project.description:
        lines.extend(["", project.description.strip()])

    for root in tree:
        lines.extend(_render_node(root, depth=0))

    if cited_ids:
        lines.extend(["", "# References", ""])
        for sid in cited_ids:
            src = sources_by_id[sid]
            lines.append(f"- **[@{_cite_key(sid)}]** {_bibliography_entry(src)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _csl_type(src: Source) -> str:
    fmt = (src.source_format or "").lower()
    if fmt in ("epub", "pdf") and not src.doi:
        return "book"
    if src.doi:
        return "article-journal"
    return "book"


def render_csl_json(sources: Iterable[Source]) -> str:
    """CSL-JSON bibliography for `pandoc --citeproc --bibliography=...`."""
    items: list[dict] = []
    for src in sources:
        item: dict = {
            "id": _cite_key(src.id),
            "type": _csl_type(src),
            "title": src.title,
        }
        if src.authors:
            item["author"] = [{"literal": a} for a in src.authors]
        if src.year:
            item["issued"] = {"date-parts": [[int(src.year)]]}
        if src.publisher:
            item["publisher"] = src.publisher
        if src.doi:
            item["DOI"] = src.doi
        if src.isbn:
            item["ISBN"] = src.isbn
        if src.language:
            item["language"] = src.language
        items.append(item)
    return json.dumps(items, ensure_ascii=False, indent=2)


def render_project_docx(
    project: Project,
    nodes: list[OutlineNode],
    evidence: list[EvidenceCard],
    sources_by_id: dict[int, Source],
    *,
    csl_style: str = "chicago",
) -> bytes:
    """Render the project to .docx via subprocess pandoc.

    Raises RuntimeError if pandoc is not on PATH or the conversion fails.
    """
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError("pandoc binary not found on PATH; install pandoc to enable DOCX export")
    csl_path = CSL_STYLES.get(csl_style)
    if not csl_path or not csl_path.exists():
        raise RuntimeError(f"unknown CSL style {csl_style!r}; choices: {sorted(CSL_STYLES)}")

    md = render_project_markdown(project, nodes, evidence, sources_by_id)
    csl_json = render_csl_json(sources_by_id.values())

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        md_path = tmp_dir / "in.md"
        bib_path = tmp_dir / "bib.json"
        out_path = tmp_dir / "out.docx"
        md_path.write_text(md, encoding="utf-8")
        bib_path.write_text(csl_json, encoding="utf-8")
        cmd = [
            pandoc,
            "--from=markdown",
            "--to=docx",
            "--citeproc",
            f"--csl={csl_path}",
            f"--bibliography={bib_path}",
            "--standalone",
            f"--output={out_path}",
            str(md_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"pandoc failed: {proc.stderr.decode('utf-8', 'replace')}")
        return out_path.read_bytes()
