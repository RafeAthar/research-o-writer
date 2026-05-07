"use client";

import Placeholder from "@tiptap/extension-placeholder";
import { Mark, Node, mergeAttributes } from "@tiptap/core";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef } from "react";

import type { EvidenceCard } from "@/lib/types";

interface Props {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  evidence?: EvidenceCard[];
}

/**
 * Citation: an inline mark wrapping text such as `[@src7]` or "Smith 2019".
 * Stores `data-source-id` so export can produce a Pandoc citation key.
 */
const Citation = Mark.create({
  name: "citation",
  inclusive: false,
  addAttributes() {
    return {
      sourceId: {
        default: null,
        parseHTML: (el) => el.getAttribute("data-source-id"),
        renderHTML: (a) =>
          a.sourceId ? { "data-source-id": a.sourceId } : {},
      },
      sourceTitle: {
        default: null,
        parseHTML: (el) => el.getAttribute("data-source-title"),
        renderHTML: (a) =>
          a.sourceTitle ? { "data-source-title": a.sourceTitle } : {},
      },
    };
  },
  parseHTML() {
    return [{ tag: "span[data-citation]" }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-citation": "true",
        class:
          "rounded bg-amber-100 px-1 py-0 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100",
      }),
      0,
    ];
  },
});

/**
 * EvidenceCard block: pins a quote with citation metadata.
 * Stores the evidence row id so export and verification can resolve it.
 */
const EvidenceBlock = Node.create({
  name: "evidenceCard",
  group: "block",
  atom: true,
  selectable: true,
  draggable: false,
  addAttributes() {
    return {
      evidenceId: {
        default: null,
        parseHTML: (el) => el.getAttribute("data-evidence-id"),
        renderHTML: (a) =>
          a.evidenceId ? { "data-evidence-id": a.evidenceId } : {},
      },
      sourceId: {
        default: null,
        parseHTML: (el) => el.getAttribute("data-source-id"),
        renderHTML: (a) =>
          a.sourceId ? { "data-source-id": a.sourceId } : {},
      },
      sourceTitle: {
        default: null,
        parseHTML: (el) => el.getAttribute("data-source-title"),
        renderHTML: (a) =>
          a.sourceTitle ? { "data-source-title": a.sourceTitle } : {},
      },
      pageStart: {
        default: null,
        parseHTML: (el) => el.getAttribute("data-page-start"),
        renderHTML: (a) =>
          a.pageStart ? { "data-page-start": a.pageStart } : {},
      },
      quote: {
        default: "",
        parseHTML: (el) => el.getAttribute("data-quote") ?? el.textContent ?? "",
        renderHTML: (a) => (a.quote ? { "data-quote": a.quote } : {}),
      },
    };
  },
  parseHTML() {
    return [{ tag: "div[data-evidence-card]" }];
  },
  renderHTML({ HTMLAttributes, node }) {
    const q = (node.attrs.quote as string) ?? "";
    const src = (node.attrs.sourceTitle as string) ?? "Source";
    const page = node.attrs.pageStart ? `, p. ${node.attrs.pageStart}` : "";
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-evidence-card": "true",
        class:
          "my-3 rounded-md border-l-4 border-blue-500 bg-blue-50 p-3 text-sm dark:bg-blue-900/20",
      }),
      [
        "blockquote",
        { class: "italic text-neutral-700 dark:text-neutral-200" },
        q,
      ],
      [
        "div",
        { class: "mt-2 text-xs text-neutral-600 dark:text-neutral-400" },
        `— ${src}${page}`,
      ],
    ];
  },
});

/**
 * DraftParagraph: a tagged paragraph variant. Renders identically to <p> but
 * carries a `data-draft="true"` attribute so the draft-view overlay can find
 * unsupported sentences and red-flag them.
 */
const DraftParagraph = Node.create({
  name: "draftParagraph",
  group: "block",
  content: "inline*",
  defining: true,
  parseHTML() {
    return [{ tag: "p[data-draft]" }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      "p",
      mergeAttributes(HTMLAttributes, {
        "data-draft": "true",
        class: "border-l-2 border-dashed border-neutral-300 pl-3",
      }),
      0,
    ];
  },
});

export default function TipTapEditor({
  value,
  onChange,
  placeholder,
  evidence,
}: Props) {
  const debounceRef = useRef<number | null>(null);
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: placeholder ?? "Write..." }),
      Citation,
      EvidenceBlock,
      DraftParagraph,
    ],
    content: value || "",
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          "prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[160px]",
      },
    },
    onUpdate: ({ editor: ed }) => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
      debounceRef.current = window.setTimeout(() => {
        onChange(ed.getHTML());
      }, 400);
    },
  });

  useEffect(() => {
    if (!editor) return;
    if (editor.getHTML() !== value) {
      editor.commands.setContent(value || "", false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  if (!editor) return null;

  const insertEvidenceBlock = (ec: EvidenceCard) => {
    editor
      .chain()
      .focus()
      .insertContent({
        type: "evidenceCard",
        attrs: {
          evidenceId: String(ec.id),
          sourceId: String(ec.source_id),
          sourceTitle:
            (ec.citation.source_title as string | undefined) ?? "Source",
          pageStart:
            (ec.citation.page_start as number | undefined) != null
              ? String(ec.citation.page_start)
              : null,
          quote: ec.quote_text,
        },
      })
      .run();
  };

  const insertCitation = (ec: EvidenceCard) => {
    const label = `[@src${ec.source_id}]`;
    editor
      .chain()
      .focus()
      .insertContent({
        type: "text",
        text: label,
        marks: [
          {
            type: "citation",
            attrs: {
              sourceId: String(ec.source_id),
              sourceTitle:
                (ec.citation.source_title as string | undefined) ?? null,
            },
          },
        ],
      })
      .run();
  };

  const toggleDraft = () => {
    const isDraft = editor.isActive("draftParagraph");
    if (isDraft) {
      editor.chain().focus().setNode("paragraph").run();
    } else {
      editor.chain().focus().setNode("draftParagraph").run();
    }
  };

  return (
    <div className="rounded border border-neutral-200 dark:border-neutral-800">
      <Toolbar
        onBold={() => editor.chain().focus().toggleBold().run()}
        onItalic={() => editor.chain().focus().toggleItalic().run()}
        onH2={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        onH3={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        onBullet={() => editor.chain().focus().toggleBulletList().run()}
        onNumbered={() => editor.chain().focus().toggleOrderedList().run()}
        onBlockquote={() => editor.chain().focus().toggleBlockquote().run()}
        onDraft={toggleDraft}
        evidence={evidence ?? []}
        onInsertEvidence={insertEvidenceBlock}
        onInsertCitation={insertCitation}
        isDraft={editor.isActive("draftParagraph")}
      />
      <div className="p-3">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}

function Toolbar(props: {
  onBold: () => void;
  onItalic: () => void;
  onH2: () => void;
  onH3: () => void;
  onBullet: () => void;
  onNumbered: () => void;
  onBlockquote: () => void;
  onDraft: () => void;
  isDraft: boolean;
  evidence: EvidenceCard[];
  onInsertEvidence: (ec: EvidenceCard) => void;
  onInsertCitation: (ec: EvidenceCard) => void;
}) {
  const btn = "rounded px-2 py-0.5 text-xs hover:bg-neutral-200 dark:hover:bg-neutral-800";
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-neutral-200 bg-neutral-50 px-2 py-1 dark:border-neutral-800 dark:bg-neutral-900">
      <button onClick={props.onBold} className={btn}><b>B</b></button>
      <button onClick={props.onItalic} className={btn}><i>I</i></button>
      <button onClick={props.onH2} className={btn}>H2</button>
      <button onClick={props.onH3} className={btn}>H3</button>
      <button onClick={props.onBullet} className={btn}>• List</button>
      <button onClick={props.onNumbered} className={btn}>1. List</button>
      <button onClick={props.onBlockquote} className={btn}>Quote</button>
      <button
        onClick={props.onDraft}
        className={`${btn} ${
          props.isDraft ? "bg-amber-100 dark:bg-amber-900/40" : ""
        }`}
        title="Mark paragraph as draft (will be checked for unsupported claims)"
      >
        Draft ¶
      </button>
      <span className="mx-1 h-4 w-px bg-neutral-300 dark:bg-neutral-700" />
      <InsertEvidenceMenu
        label="Insert evidence"
        evidence={props.evidence}
        onPick={props.onInsertEvidence}
      />
      <InsertEvidenceMenu
        label="Cite"
        evidence={props.evidence}
        onPick={props.onInsertCitation}
      />
    </div>
  );
}

function InsertEvidenceMenu({
  label,
  evidence,
  onPick,
}: {
  label: string;
  evidence: EvidenceCard[];
  onPick: (ec: EvidenceCard) => void;
}) {
  return (
    <div className="relative inline-block group">
      <button className="rounded px-2 py-0.5 text-xs hover:bg-neutral-200 dark:hover:bg-neutral-800">
        {label} ▾
      </button>
      <div className="absolute left-0 top-full z-10 hidden max-h-72 w-72 overflow-y-auto rounded border border-neutral-300 bg-white p-1 text-xs shadow-lg group-hover:block dark:border-neutral-700 dark:bg-neutral-900">
        {evidence.length === 0 ? (
          <div className="p-2 text-neutral-500">No pinned evidence yet.</div>
        ) : (
          <ul>
            {evidence.map((ec) => (
              <li key={ec.id}>
                <button
                  onClick={() => onPick(ec)}
                  className="block w-full truncate px-2 py-1 text-left hover:bg-neutral-100 dark:hover:bg-neutral-800"
                  title={ec.quote_text}
                >
                  <span className="font-medium">
                    {(ec.citation.source_title as string | undefined) ?? "Source"}
                  </span>
                  : {ec.quote_text.slice(0, 60)}…
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
