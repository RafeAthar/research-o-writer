import Link from "next/link";

export default function HomePage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-10">
      <h1 className="text-3xl font-semibold tracking-tight">Research-o-Writer</h1>
      <p className="text-neutral-600 dark:text-neutral-400">
        Upload books and articles, chat with citations grounded in your library, and build outlines
        backed by pinned evidence.
      </p>
      <ul className="grid gap-3 sm:grid-cols-3">
        <li>
          <Link
            href="/library"
            className="block rounded-lg border border-neutral-200 p-4 hover:border-neutral-400 dark:border-neutral-800 dark:hover:border-neutral-600"
          >
            <div className="font-medium">Library</div>
            <div className="text-xs text-neutral-500">Sources & ingestion</div>
          </Link>
        </li>
        <li>
          <Link
            href="/chat"
            className="block rounded-lg border border-neutral-200 p-4 hover:border-neutral-400 dark:border-neutral-800 dark:hover:border-neutral-600"
          >
            <div className="font-medium">Chat</div>
            <div className="text-xs text-neutral-500">Grounded Q&amp;A</div>
          </Link>
        </li>
        <li>
          <Link
            href="/projects"
            className="block rounded-lg border border-neutral-200 p-4 hover:border-neutral-400 dark:border-neutral-800 dark:hover:border-neutral-600"
          >
            <div className="font-medium">Projects</div>
            <div className="text-xs text-neutral-500">Outlines & evidence</div>
          </Link>
        </li>
      </ul>
    </div>
  );
}
