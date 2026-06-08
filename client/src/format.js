// format.js — small presentation helpers (keep formatting out of components).

const TRY = new Intl.NumberFormat("tr-TR", {
  style: "currency",
  currency: "TRY",
  maximumFractionDigits: 0,
});

const NUM = new Intl.NumberFormat("tr-TR");

export function money(value) {
  if (value === null || value === undefined) return "—";
  return TRY.format(value);
}

// Signed money for price differences (+/- prefix).
export function moneySigned(value) {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return sign + TRY.format(value);
}

export function num(value) {
  if (value === null || value === undefined) return "—";
  return NUM.format(value);
}

export function dateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Map the controlled English verdict enum to display label + CSS modifier.
export function verdictMeta(verdict) {
  switch (verdict) {
    case "DEAL":
      return { label: "FIRSAT", cls: "v-deal" };
    case "OVERPRICED":
      return { label: "PAHALI", cls: "v-over" };
    case "FAIR":
    default:
      return { label: "MAKUL", cls: "v-fair" };
  }
}
