"use client";

import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useRef } from "react";

interface Props {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}

/**
 * Minimal TipTap editor. Stores rich content as HTML; conversion to markdown
 * happens at export time. Debounces parent updates.
 */
export default function TipTapEditor({ value, onChange, placeholder }: Props) {
  const debounceRef = useRef<number | null>(null);
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: placeholder ?? "Write..." }),
    ],
    content: value || "",
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          "prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[120px]",
      },
    },
    onUpdate: ({ editor: ed }) => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
      debounceRef.current = window.setTimeout(() => {
        onChange(ed.getHTML());
      }, 400);
    },
  });

  // Sync external value changes (e.g. switching nodes).
  useEffect(() => {
    if (!editor) return;
    if (editor.getHTML() !== value) {
      editor.commands.setContent(value || "", false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  if (!editor) return null;

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
}) {
  const btn = "rounded px-2 py-0.5 text-xs hover:bg-neutral-200 dark:hover:bg-neutral-800";
  return (
    <div className="flex flex-wrap gap-1 border-b border-neutral-200 bg-neutral-50 px-2 py-1 dark:border-neutral-800 dark:bg-neutral-900">
      <button onClick={props.onBold} className={btn}><b>B</b></button>
      <button onClick={props.onItalic} className={btn}><i>I</i></button>
      <button onClick={props.onH2} className={btn}>H2</button>
      <button onClick={props.onH3} className={btn}>H3</button>
      <button onClick={props.onBullet} className={btn}>• List</button>
      <button onClick={props.onNumbered} className={btn}>1. List</button>
      <button onClick={props.onBlockquote} className={btn}>Quote</button>
    </div>
  );
}
