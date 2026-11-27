import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="rounded-xl border border-white/[0.08] bg-[#111A25] p-6 sm:p-8">
      <p className="text-xs font-medium tracking-[0.16em] text-[#8B9BB0] uppercase">404 · Page not found</p>
      <h1 className="mt-3 font-display text-2xl font-semibold text-[#F1F3F5]">This page does not exist</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#8B9BB0]">
        The requested page is not part of the application.
      </p>
      <Link
        to="/overview"
        className="mt-5 inline-flex rounded-lg border border-white/[0.1] px-3 py-2 text-sm text-[#F1F3F5] transition hover:bg-white/[0.06]"
      >
        Return to overview
      </Link>
    </section>
  );
}
