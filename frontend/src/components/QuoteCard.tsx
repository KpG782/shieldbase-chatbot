import type { QuoteResult } from "../types";

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number") {
    return new Intl.NumberFormat("en-US").format(value);
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    return value.map(formatValue).join(", ");
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }

  return "";
}

function formatCurrency(result: QuoteResult): string | null {
  const premium =
    typeof result.premium === "number"
      ? result.premium
      : typeof result.annual_premium === "number"
        ? result.annual_premium
        : null;

  if (premium === null) {
    return null;
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: result.currency || "USD"
  }).format(premium);
}

interface QuoteCardProps {
  quote: QuoteResult | null;
  variant?: "spotlight" | "embedded";
}

const PRIORITY_FIELDS = [
  "coverage_level",
  "vehicle",
  "vehicle_year",
  "vehicle_make",
  "vehicle_model",
  "deductible",
  "term_years",
  "policy_type"
];

export function QuoteCard({
  quote,
  variant = "embedded"
}: QuoteCardProps) {
  const cardClassName =
    variant === "spotlight"
      ? "ui-scale-in ui-sheen rounded-[1.5rem] border border-black/8 bg-white/95 p-5 text-slate-900 shadow-[0_16px_44px_rgba(15,23,42,0.08)] backdrop-blur"
      : "ui-scale-in rounded-[1.25rem] border border-black/8 bg-[#fbfbf8] p-4 shadow-[0_8px_24px_rgba(15,23,42,0.05)]";

  if (!quote) {
    return (
      <section className={cardClassName}>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Quote summary
        </p>
        <p className="mt-3 text-sm text-slate-500">Draft quote in progress.</p>
        <div className="mt-4 rounded-xl border border-dashed border-slate-300 px-3 py-4 text-center text-sm text-slate-400">
          Waiting for premium
        </div>
      </section>
    );
  }

  const premium = formatCurrency(quote);
  const summary = quote.summary || quote.product_type || "Insurance quote";

  const filteredEntries = Object.entries(quote).filter(
    ([key, value]) =>
      ![
        "summary",
        "product_type",
        "premium",
        "annual_premium",
        "currency"
      ].includes(key) && value !== undefined && value !== null && value !== ""
  );

  const entries = filteredEntries
    .sort(([left], [right]) => {
      const leftIndex = PRIORITY_FIELDS.indexOf(left);
      const rightIndex = PRIORITY_FIELDS.indexOf(right);

      return (leftIndex === -1 ? 999 : leftIndex) - (rightIndex === -1 ? 999 : rightIndex);
    })
    .slice(0, variant === "spotlight" ? 6 : 4);

  return (
    <section className={`${cardClassName} min-w-0`}>
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        Quote summary
      </p>
      <h2 className="mt-2 break-words text-base font-semibold text-slate-900">
        {summary}
      </h2>
      {premium ? (
        <p className="mt-3 break-words text-2xl font-semibold tracking-[-0.04em] text-emerald-700 sm:text-3xl">
          {premium}
        </p>
      ) : null}
      {entries.length ? (
        <dl className="mt-4 grid gap-2">
          {entries.map(([key, value]) => (
            <div
              key={key}
              className="ui-hover-lift rounded-xl border border-slate-200/80 bg-slate-50/80 px-3 py-2.5"
            >
              <dt className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                {key.replace(/_/g, " ")}
              </dt>
              <dd className="mt-1 break-words text-sm text-slate-900" style={{ overflowWrap: "anywhere" }}>
                {formatValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      {filteredEntries.length > entries.length ? (
        <p className="mt-4 text-xs text-slate-500">
          Showing the key quote details in chat. Open confirmation for the full review.
        </p>
      ) : null}
    </section>
  );
}
