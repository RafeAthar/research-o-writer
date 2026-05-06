export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 p-10">
      <h1 className="text-3xl font-semibold tracking-tight">Research-o-Writer</h1>
      <p className="text-neutral-600 dark:text-neutral-400">
        A source-grounded research and writing workspace. Phase 1 is under construction.
      </p>
      <ul className="list-disc space-y-1 pl-6 text-sm text-neutral-700 dark:text-neutral-300">
        <li>
          <a className="underline" href="/library">
            Library
          </a>{" "}
          — manage your sources
        </li>
        <li>
          <a className="underline" href="/chat">
            Chat
          </a>{" "}
          — ask grounded questions
        </li>
        <li>
          <a className="underline" href="/projects">
            Projects
          </a>{" "}
          — outlines and evidence
        </li>
      </ul>
    </main>
  );
}
