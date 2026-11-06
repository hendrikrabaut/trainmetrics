import { api } from "../api.js";
import { barChart } from "../charts.js";
import { h, message, tile } from "../dom.js";
import { SPORTS, dayLabel, decimal, duration, isoDay, kilometers } from "../format.js";

const MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];

function heatmap(review) {
  const year = review.year;
  const first = new Date(year, 0, 1, 12);
  const lead = (first.getDay() + 6) % 7;
  const highest = Math.max(1, ...Object.values(review.days));
  const cells = [];

  for (let index = 0; index < lead; index += 1) cells.push(h("i", { class: "heat-blank" }));

  for (const day = new Date(first); day.getFullYear() === year; day.setDate(day.getDate() + 1)) {
    const key = isoDay(day);
    const effort = review.days[key] ?? 0;
    const level = effort ? Math.min(4, Math.ceil((effort / highest) * 4)) : 0;

    cells.push(h("i", {
      class: `heat-${level}`,
      title: `${dayLabel(key)}${effort ? `: inspanning ${effort}` : ": geen training"}`,
    }));
  }

  return h("div", { class: "heat-scroll" },
    h("div", { class: "heatmap", role: "img", "aria-label": `Elke trainingsdag van ${year}, donkerder is zwaarder` }, cells),
    h("div", { class: "heat-legend muted" }, "Licht", [1, 2, 3, 4].map((level) => h("i", { class: `heat-${level}` })), "Zwaar")
  );
}

function reviewBody(review) {
  const today = new Date();

  if (!review.workouts) return h("p", { class: "muted" }, "Geen trainingen in dit jaar.");

  const highlights = [
    review.longest && ["Verste training", `${kilometers(review.longest.meters)} ${SPORTS[review.longest.sport].toLowerCase()}, ${dayLabel(review.longest.date)}`],
    review.hardest && ["Zwaarste training", `${SPORTS[review.hardest.sport]}, ${dayLabel(review.hardest.date)}`],
    review.busiest_week && ["Drukste week", `Week van ${dayLabel(review.busiest_week.week_start)}: ${duration(review.busiest_week.seconds)}`],
  ].filter(Boolean);

  const unfinished = review.year === today.getFullYear();

  return h("div", {},
    h("div", { class: "year-hero" },
      h("span", {}, unfinished ? `${review.year} tot nu toe` : String(review.year)),
      h("strong", {}, duration(review.seconds)),
      h("span", {}, `op ${review.active_days} dagen, ${review.workouts} trainingen`)
    ),
    h("div", { class: "tiles" },
      tile(kilometers(review.meters), "afstand"),
      tile(`${decimal(review.ascent, 0)} m`, "geklommen"),
      tile(String(review.active_weeks), "actieve weken")
    ),
    h("h3", {}, "Elke dag van het jaar"),
    heatmap(review),
    h("div", { style: "margin-top:16px" }, barChart("Trainingstijd per maand", review.months, {
      x: (month) => MONTHS[month.month - 1],
      y: (month) => month.seconds / 3600,
      format: (value) => `${decimal(value)} u`,
      tip: (month) => MONTHS[month.month - 1],
      columns: [
        { label: "Maand", value: (month) => MONTHS[month.month - 1] },
        { label: "Tijd", value: (month) => duration(month.seconds) },
        { label: "Afstand", value: (month) => kilometers(month.meters) },
      ],
    })),
    h("h3", { style: "margin-top:16px" }, "Per sport"),
    h("div", { class: "tiles" }, review.sports.map((row) =>
      tile(row.meters ? kilometers(row.meters) : duration(row.seconds), `${SPORTS[row.sport]}, ${row.sessions}×`))),
    h("h3", {}, "Hoogtepunten"),
    h("ul", { class: "highlights" }, highlights.map(([label, text]) =>
      h("li", {}, h("b", {}, `${label}: `), text)))
  );
}

export function yearPanel() {
  const body = h("div", {});
  const select = h("select", { "aria-label": "Jaar", style: "width:auto" });

  const load = async (year) => {
    try {
      const review = await api(`/api/analytics/year/${year}`);

      if (!select.options.length) {
        for (const option of review.years.length ? review.years : [year]) {
          select.append(h("option", { value: option }, String(option)));
        }
      }

      select.value = String(year);
      body.replaceChildren(reviewBody(review));
    } catch (error) {
      body.replaceChildren(message(error.message, true));
    }
  };

  select.addEventListener("change", () => load(Number(select.value)));
  load(new Date().getFullYear());

  return h("section", { class: "card" },
    h("div", { class: "row spread", style: "margin-bottom:12px" },
      h("h2", { style: "margin:0" }, "Terugblik op je jaar"),
      select
    ),
    body
  );
}
