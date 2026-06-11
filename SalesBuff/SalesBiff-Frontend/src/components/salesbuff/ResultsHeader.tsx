import type { SalesBrief } from "@/lib/api/research.functions";
import { Quote } from "lucide-react";

export function ResultsHeader({ brief }: { brief: SalesBrief }) {
  const { subject, opening_line } = brief;
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm results-subject">
        <Field label="Prospect" value={subject.prospect} />
        <Dot />
        <Field label="Contact" value={subject.contact} />
        <Dot />
        <Field label="Incumbent" value={subject.incumbent ?? "—"} />
      </div>

      <div className="skeuo-callout p-6 relative">
        <Quote
          className="absolute top-4 left-4 text-[var(--sb-callout-quote)] opacity-30"
          size={36}
        />
        <div className="pl-12">
          <div className="text-[0.7rem] uppercase tracking-[0.18em] font-bold text-[var(--sb-callout-eyebrow)] mb-1.5">
            Opening line
          </div>
          <p className="font-display text-xl md:text-2xl leading-snug font-semibold text-[var(--salesbuff-ink)]">
            {opening_line}
          </p>
        </div>
      </div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <span className="result-field-label text-[0.7rem] uppercase tracking-wider font-bold text-[var(--sb-eyebrow-strong)] mr-1.5">
        {label}
      </span>
      <span className="font-sans text-lg font-semibold text-[var(--sb-subject)]">{value}</span>
    </span>
  );
}
function Dot() {
  return <span className="text-[var(--salesbuff-ink-soft)]">•</span>;
}
