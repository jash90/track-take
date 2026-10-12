import { Link } from "react-router";

export function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-6 py-24">
      <div className="eyebrow">404</div>
      <h1 className="mt-2 font-display text-5xl italic">Ta klatka nie istnieje.</h1>
      <Link to="/" className="mt-6 inline-block text-safe underline-offset-4 hover:underline">
        ← Wróć do projektów
      </Link>
    </div>
  );
}
