export function TypingIndicator() {
  return (
    <span className="inline-flex items-center gap-1.5" aria-label="Assistant is typing">
      <span className="h-2 w-2 animate-bounce rounded-full bg-cyan-500 [animation-delay:-0.25s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-cyan-500 [animation-delay:-0.1s]" />
      <span className="h-2 w-2 animate-bounce rounded-full bg-cyan-500" />
    </span>
  );
}
