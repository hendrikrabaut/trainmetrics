import { api } from "../api.js";
import { fields, h, submitter, table } from "../dom.js";
import { PHASE_LABELS, RACE_GOALS, dayLabel, isoDay } from "../format.js";
import { route } from "../navigation.js";

const PRIORITIES = {
  A: "A: hoofddoel",
  B: "B: tussendoel",
  C: "C: als training",
};

const GOAL_OPTIONS = {
  "": "Andere afstand",
  ...RACE_GOALS,
};

function phaseBar(plan) {
  const blocks = [];

  for (const week of plan.weeks) {
    const last = blocks.at(-1);

    if (last?.phase === week.phase) last.weeks += 1;
    else blocks.push({ phase: week.phase, weeks: 1 });
  }

  return h("div", { class: "phase-bar", role: "img", "aria-label": blocks.map((block) => `${PHASE_LABELS[block.phase]} ${block.weeks} weken`).join(", ") },
    blocks.map((block) =>
      h("div", { class: `phase ${block.phase}`, style: `flex:${block.weeks}` },
        h("span", {}, PHASE_LABELS[block.phase] ?? block.phase),
        h("small", {}, `${block.weeks} wk`))
    ));
}

export function seasonPanel(plan, races) {
  const today = isoDay(new Date());

  const remove = async (race) => {
    if (!confirm(`${race.name} verwijderen?`)) return;

    await api(`/api/races/${race.id}`, { method: "DELETE" });
    route();
  };

  const daysUntil = (date) =>
    Math.round((new Date(`${date}T12:00:00`) - new Date(`${today}T12:00:00`)) / 86400000);

  return h("section", { class: "card" },
    h("h2", {}, "Seizoen"),
    plan?.weeks?.some((week) => week.phase) && h("div", { style: "margin-bottom:16px" },
      h("h3", {}, `Fases van je plan: ${plan.goal_name}`),
      phaseBar(plan),
      h("p", { class: "muted", style: "margin:8px 0 0" },
        "Basis legt het fundament met rustige kilometers, opbouw voegt snelheid toe, piek wordt specifiek voor je wedstrijd en afbouw maakt je fris.")
    ),
    h("h3", {}, "Wedstrijden"),
    races.length > 0 && table([
      { label: "Wedstrijd", value: (race) => race.name },
      { label: "Prioriteit", value: (race) => race.priority },
      { label: "Datum", value: (race) => dayLabel(race.date) },
      {
        label: "Over",
        value: (race) => {
          const days = daysUntil(race.date);
          return days < 0 ? "geweest" : `${days} dagen`;
        },
      },
      {
        label: "",
        value: (race) => h("button", {
          class: "danger small", type: "button", onclick: () => remove(race),
        }, "Verwijderen"),
      },
    ], races),
    h("form", {
      style: "margin-top:12px",
      onsubmit: submitter(async (form) => {
        const values = fields(form);

        await api("/api/races/", {
          json: {
            name: values.name,
            date: values.date,
            priority: values.priority,
            goal: values.goal || null,
          },
        });

        route();
      }),
    },
      h("div", { class: "fields" },
        h("label", {}, "Naam", h("input", { name: "name", required: true })),
        h("label", {}, "Datum", h("input", { name: "date", type: "date", required: true })),
        h("label", {}, "Prioriteit",
          h("select", { name: "priority" },
            Object.entries(PRIORITIES).map(([key, label]) => h("option", { value: key }, label)))),
        h("label", {}, "Afstand",
          h("select", { name: "goal" },
            Object.entries(GOAL_OPTIONS).map(([key, label]) => h("option", { value: key }, label))))
      ),
      h("div", {}, h("button", { class: "primary", type: "submit" }, "Wedstrijd toevoegen"))
    ),
    h("p", { class: "muted", style: "margin:12px 0 0" },
      "Maak je daarna een nieuw plan, dan richt het zich op je wedstrijd en maakt het de week van een B- of C-wedstrijd lichter.")
  );
}
