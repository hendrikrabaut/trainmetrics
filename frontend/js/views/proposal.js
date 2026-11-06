import { api } from "../api.js";
import { chooseTab, fields, h, message, submitter } from "../dom.js";
import { PLAN_GOALS, SPORTS, dayLabel, isoDay, kilometers, localNow } from "../format.js";
import { route } from "../navigation.js";
import { pickedDays, weekdayPicker } from "./weekdays.js";

const SOURCE_LABELS = { MODEL: "AI", RULES: "Regels", USER: "Jij" };

function requestForm(races) {
  const coming = races.filter((race) => race.date > localNow().slice(0, 10));
  const status = h("div", { "aria-live": "polite" });

  const ask = async (form, useModel) => {
    const values = fields(form);
    const weekdays = pickedDays(form);
    const race = coming.find((item) => String(item.id) === values.race);

    if (weekdays.length < 2) throw new Error("Kies minstens twee dagen");

    status.replaceChildren(message(useModel
      ? "De coach stelt een schema op. Op een laptop kan dat enkele minuten duren."
      : "Even geduld..."));

    try {
      const proposal = await api("/api/plans/proposal", {
        json: {
          goal: race?.goal ?? values.goal,
          weekdays,
          start_date: values.start_date || null,
          weeks: race || values.race_date || !values.weeks ? null : Number(values.weeks),
          race_date: race?.date ?? (values.race_date || null),
          notes: values.notes || null,
          use_model: useModel,
        },
      });

      lastModelError = proposal.model_error;
      chooseTab("plan", "Voorstel");
      route();
    } finally {
      status.replaceChildren();
    }
  };

  const form = h("form", {
    onsubmit: submitter((element) => ask(element, true)),
  },
    h("div", { class: "fields" },
      h("label", {}, "Doel",
        h("select", { name: "goal" },
          Object.entries(PLAN_GOALS).map(([key, label]) => h("option", { value: key }, label)))),
      coming.length > 0 && h("label", {}, "Richt op wedstrijd",
        h("select", { name: "race" },
          h("option", { value: "" }, "Geen"),
          coming.map((race) => h("option", { value: race.id }, `${race.priority}: ${race.name}, ${dayLabel(race.date)}`)))),
      h("label", {}, "Wedstrijddatum (optioneel)", h("input", { name: "race_date", type: "date" })),
      h("label", {}, "Of aantal weken", h("input", {
        name: "weeks", type: "number", min: 2, max: 30, placeholder: "Automatisch", inputmode: "numeric",
      })),
      h("label", {}, "Start vanaf", h("input", {
        name: "start_date", type: "date", value: localNow().slice(0, 10),
      }))
    ),
    weekdayPicker([1, 3, 5, 6]),
    h("label", {}, "Wensen voor de coach (optioneel)", h("textarea", {
      name: "notes",
      rows: 2,
      maxlength: 1000,
      placeholder: "Bijvoorbeeld: ik wil vandaag en zondag ook gaan lopen",
    })),
    status,
    h("div", { class: "row" },
      h("button", { class: "primary", type: "submit" }, "Vraag voorstel"),
      h("button", {
        class: "small",
        type: "button",
        onclick: (event) => {
          const element = event.currentTarget.form;

          if (element.reportValidity()) {
            ask(element, false).catch((error) => {
              status.replaceChildren(message(error.message, true));
            });
          }
        },
      }, "Zonder AI, met vaste regels")
    ),
    h("p", { class: "muted", style: "margin:0" },
      "Een voorstel verandert niets aan je planning. Jij past het aan en keurt het goed.")
  );

  return form;
}

// Why the model did not help, for the proposal that was just made.
let lastModelError = null;

function newRow(rows) {
  const last = rows.at(-1)?.date ?? localNow().slice(0, 10);
  const day = new Date(`${last}T12:00:00`);
  day.setDate(day.getDate() + 1);

  return {
    date: isoDay(day),
    sport: "RUNNING",
    title: "Nieuwe training",
    description: "",
    distance: null,
    duration: null,
    phase: null,
    source: "USER",
  };
}

function weekSummary(rows) {
  const meters = rows.reduce((sum, row) => sum + (row.distance ?? 0), 0);

  return [`${rows.length} ${rows.length === 1 ? "training" : "trainingen"}`, meters ? kilometers(meters) : null]
    .filter(Boolean)
    .join(" · ");
}

function mondayOf(date) {
  const day = new Date(`${date}T12:00:00`);
  day.setDate(day.getDate() - ((day.getDay() + 6) % 7));
  return isoDay(day);
}

function proposalEditor(proposal, hasPlan) {
  const rows = proposal.sessions.map((row) => ({ ...row }));
  const warnings = h("div", { "aria-live": "polite" });
  const list = h("div", {});
  const failure = h("div", { "aria-live": "polite" });

  let saving = Promise.resolve();

  const showWarnings = (items) => {
    warnings.replaceChildren(...(items.length
      ? [h("div", { class: "message proposal-warnings" },
        h("strong", {}, "Let hierop"),
        h("ul", {}, items.map((item) => h("li", {}, item))))]
      : []));
  };

  // One at a time and in order, so an older save never overwrites a newer one.
  const save = () => {
    saving = saving.then(async () => {
      try {
        failure.replaceChildren();
        const updated = await api("/api/plans/proposal", {
          method: "PUT",
          json: { sessions: rows },
        });
        showWarnings(updated.warnings);
      } catch (error) {
        failure.replaceChildren(message(error.message, true));
        throw error;
      }
    });

    return saving.catch(() => {});
  };

  const rowElement = (row) => {
    const change = (field, parse = (value) => value) => (event) => {
      row[field] = parse(event.target.value);
      row.source = "USER";
      event.target.closest(".proposal-row").querySelector(".source-tag").textContent = SOURCE_LABELS.USER;
      save();
    };

    return h("div", { class: "proposal-row" },
      h("label", {}, "Dag", h("input", {
        type: "date", value: row.date, required: true, onchange: change("date"),
      })),
      h("label", {}, "Sport", (() => {
        const select = h("select", { onchange: change("sport") },
          Object.entries(SPORTS).map(([key, label]) => h("option", { value: key }, label)));
        select.value = row.sport;
        return select;
      })()),
      h("label", { class: "proposal-title" }, "Training", h("input", {
        value: row.title, maxlength: 100, required: true, onchange: change("title"),
      })),
      h("label", {}, "km", h("input", {
        type: "number", min: 0, step: "0.1", inputmode: "decimal",
        value: row.distance ? String(Math.round(row.distance / 100) / 10) : "",
        onchange: change("distance", (value) => (value ? Math.round(Number(value) * 1000) : null)),
      })),
      h("label", {}, "min", h("input", {
        type: "number", min: 0, inputmode: "numeric",
        value: row.duration ? String(Math.round(row.duration / 60)) : "",
        onchange: change("duration", (value) => (value ? Math.round(Number(value) * 60) : null)),
      })),
      h("label", { class: "proposal-description" }, "Uitleg", h("input", {
        value: row.description ?? "", maxlength: 500, onchange: change("description"),
      })),
      h("div", { class: "proposal-actions" },
        h("span", { class: "source-tag", title: "Waar dit vandaan komt" }, SOURCE_LABELS[row.source] ?? "AI"),
        h("button", {
          class: "danger small",
          type: "button",
          "aria-label": `${row.title} verwijderen uit het voorstel`,
          onclick: () => {
            rows.splice(rows.indexOf(row), 1);
            render();
            save();
          },
        }, "×")
      )
    );
  };

  const render = () => {
    rows.sort((one, other) => one.date.localeCompare(other.date));

    const weeks = new Map();

    for (const row of rows) {
      const monday = mondayOf(row.date);
      if (!weeks.has(monday)) weeks.set(monday, []);
      weeks.get(monday).push(row);
    }

    list.replaceChildren(...[...weeks.entries()].map(([monday, weekRows], index) =>
      h("details", { class: "week proposal-week", open: index < 3 },
        h("summary", {}, `Week van ${dayLabel(monday, { day: "numeric", month: "short" })} · ${weekSummary(weekRows)}`),
        weekRows.map(rowElement))));
  };

  render();
  showWarnings(proposal.warnings);

  const sourceText = {
    MODEL: "Voorstel van het taalmodel, op basis van je data.",
    MIXED: "De eerste weken komen van het taalmodel, de latere uit de vaste regels.",
    RULES: "Dit voorstel komt uit de vaste regels, niet van het taalmodel.",
  }[proposal.source];

  return h("section", { class: "card proposal" },
    h("div", { class: "row spread" },
      h("h2", { style: "margin:0" }, `Voorstel: ${proposal.goal_name}`),
      h("span", { class: "muted" }, `${rows.length} trainingen, nog niet in je planning`)
    ),
    h("p", { class: "muted" }, sourceText),
    proposal.source === "RULES" && lastModelError && message(
      "Het taalmodel was niet bereikbaar. Staat de laptop aan en draait Ollama? Probeer het later opnieuw."),
    proposal.source === "RULES" && proposal.notes && message(
      `De vaste regels lezen je wens niet: "${proposal.notes}". Pas het schema hieronder zelf aan.`),
    proposal.rationale && h("p", {}, proposal.rationale),
    warnings,
    failure,
    list,
    h("div", { class: "row", style: "margin-top:12px" },
      h("button", {
        class: "small",
        type: "button",
        onclick: () => {
          rows.push(newRow(rows));
          render();
          save();
        },
      }, "Training toevoegen")
    ),
    h("div", { class: "row proposal-decision" },
      h("button", {
        class: "primary",
        type: "button",
        onclick: async () => {
          if (hasPlan && !confirm("Dit voorstel vervangt je huidige plan vanaf vandaag. Wat je al deed, blijft meetellen. Doorgaan?")) {
            return;
          }

          try {
            await saving;
            await api("/api/plans/proposal/approve", { method: "POST" });
            chooseTab("plan", "Schema");
            route();
          } catch (error) {
            failure.replaceChildren(message(error.message, true));
          }
        },
      }, "Zet in mijn planning"),
      h("button", {
        class: "danger small",
        type: "button",
        onclick: async () => {
          if (!confirm("Dit voorstel weggooien?")) return;

          await api("/api/plans/proposal", { method: "DELETE" });
          route();
        },
      }, "Weggooien")
    )
  );
}

export function proposalTab(proposal, races, hasPlan) {
  return [
    proposal && proposalEditor(proposal, hasPlan),
    h("details", { class: "card form-toggle", open: !proposal },
      h("summary", {}, proposal ? "Nieuw voorstel vragen" : "Vraag een voorstel"),
      requestForm(races)
    ),
  ];
}
