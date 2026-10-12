import { Link } from "react-router";
import { useT } from "../i18n";

export function NotFound() {
  const t = useT();
  return (
    <div className="mx-auto max-w-xl px-6 py-24">
      <div className="eyebrow">404</div>
      <h1 className="mt-2 font-display text-5xl italic">{t("notFound.title")}</h1>
      <Link to="/" className="mt-6 inline-block text-safe underline-offset-4 hover:underline">
        {t("notFound.back")}
      </Link>
    </div>
  );
}
