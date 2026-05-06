export interface Source {
  id: number;
  title: string;
  authors: string[];
  year: number | null;
  publisher: string | null;
  isbn: string | null;
  doi: string | null;
  language: string | null;
  source_format: string;
  page_count: number | null;
  word_count: number | null;
  status: string;
  ingestion_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface StructureNode {
  id: number;
  parent_id: number | null;
  title: string;
  chapter_path: string[];
  depth: number;
  order_in_parent: number;
  page_start: number | null;
  page_end: number | null;
}

export interface ChunkRow {
  id: number;
  source_id: number;
  chapter_path: string[];
  page_start: number | null;
  page_end: number | null;
  paragraph_index: number | null;
  char_start: number | null;
  char_end: number | null;
  text: string;
}

export interface Highlight {
  id: number;
  source_id: number;
  chunk_id: number | null;
  page: number | null;
  char_start: number | null;
  char_end: number | null;
  text: string;
  note: string | null;
  color: string | null;
  created_at: string;
}

export interface Quote {
  id: number;
  source_id: number;
  chunk_id: number | null;
  text: string;
  citation: Record<string, unknown>;
  note: string | null;
  created_at: string;
}

export interface SearchHit {
  chunk_id: number;
  source_id: number;
  source_title: string;
  chapter_path: string[];
  page_start: number | null;
  page_end: number | null;
  paragraph_index: number | null;
  char_start: number | null;
  char_end: number | null;
  text: string;
  score: number;
}

export interface ChatPassage {
  id: number;
  chunk_id: number;
  source_id: number;
  source_title: string;
  chapter_path: string[];
  page_start: number | null;
  page_end: number | null;
  paragraph_index: number | null;
  char_start: number | null;
  char_end: number | null;
  score: number;
  preview: string;
}

export interface ChatCitation {
  passage: number;
  chunk_id: number;
  source_id: number;
  source_title: string;
  chapter_path: string[];
  page_start: number | null;
  page_end: number | null;
  paragraph_index: number | null;
  char_start: number | null;
  char_end: number | null;
  preview: string;
}

export interface Chat {
  id: number;
  title: string;
  scope: "library" | "sources" | "project";
  source_ids: number[];
  project_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  model: string | null;
  error: string | null;
  created_at: string;
}

export interface Project {
  id: number;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface OutlineNode {
  id: number;
  project_id: number;
  parent_id: number | null;
  title: string;
  kind: string;
  order_in_parent: number;
  body_md: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceCard {
  id: number;
  outline_node_id: number;
  source_id: number;
  chunk_id: number | null;
  quote_text: string;
  citation: Record<string, unknown>;
  note: string | null;
  order_in_node: number;
  created_at: string;
}
