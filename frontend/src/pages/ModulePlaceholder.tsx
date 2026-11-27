interface ModulePlaceholderProps {
  title: string;
  description: string;
}

export function ModulePlaceholder({ title, description }: ModulePlaceholderProps) {
  return (
    <section className="rounded-xl border border-white/[0.08] bg-[#111A25] p-6 sm:p-8">
      <p className="text-xs font-medium tracking-[0.16em] text-[#52D6A0] uppercase">
        Module in development
      </p>
      <h1 className="mt-3 font-display text-2xl font-semibold text-[#F1F3F5]">{title}</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#8B9BB0]">{description}</p>
      <p className="mt-5 border-t border-white/[0.08] pt-4 text-xs text-[#8B9BB0]">
        No market or trading data is displayed until this module is implemented.
      </p>
    </section>
  );
}
