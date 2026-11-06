import { proposalTab } from "./proposal.js";
import { pickedDays, weekdayPicker } from "./weekdays.js";
import { addSessionForm, calendarPanel } from "./calendar.js";
import { seasonPanel } from "./season.js";
import { api } from "../api.js";
import { art, coachDialog } from "../art.js";
import { fields, h, message, subTabs, submitter } from "../dom.js";
import { PHASE_LABELS, PLAN_GOALS, SPORTS, dayLabel, duration, kilometers, localNow } from "../format.js";
import { xpBar } from "../gamification.js";
import { route } from "../navigation.js";


function complianceText(session) {
  const actual = session.actual;

  if (!actual) return null;

  const planned = session.distance
    ? `gepland ${kilometers(session.distance)}, gedaan ${actual.distance ? kilometers(actual.distance) : "?"}`
    : session.duration
      ? `gepland ${duration(session.duration)}, gedaan ${duration(actual.duration)}`
      : `gedaan op ${dayLabel(actual.date, { weekday: "short", day: "numeric", month: "short" })}`;

  return actual.ratio === null ? planned : `${planned} (${Math.round(actual.ratio * 100)}%)`;
}

function sessionRow(session) {
  const state = session.completed ? "completed" : session.partial ? "partial" : session.missed ? "missed" : "";

  const details = [
    session.distance ? kilometers(session.distance) : null,
    session.duration ? duration(session.duration) : null,
  ].filter(Boolean);

  const editor = h("form", {
    class: "session-edit",
    hidden: true,
    onsubmit: submitter(async (form) => {
      const values = fields(form);

      await api(`/api/plans/sessions/${session.id}`, {
        method: "PATCH",
        json: {
          date: values.date,
          distance: values.km ? Number(values.km) * 1000 : null,
          duration: values.minutes ? Math.round(values.minutes * 60) : null,
        },
      });

      route();
    }),
  },
    h("div", { class: "fields" },
      h("label", {}, "Dag", h("input", { name: "date", type: "date", value: session.date, required: true })),
      h("label", {}, "Afstand (km)", h("input", {
        name: "km", type: "number", min: 0, step: "0.1", inputmode: "decimal",
        value: session.distance ? String(session.distance / 1000) : "",
      })),
      h("label", {}, "Duur (min)", h("input", {
        name: "minutes", type: "number", min: 0, inputmode: "numeric",
        value: session.duration ? String(Math.round(session.duration / 60)) : "",
      }))
    ),
    h("div", { class: "row" },
      h("button", { class: "primary small", type: "submit" }, "Opslaan"),
      h("button", {
        class: "danger small",
        type: "button",
        onclick: async () => {
          if (!confirm(`${session.title} verwijderen uit je plan?`)) return;

          try {
            await api(`/api/plans/sessions/${session.id}`, { method: "DELETE" });
            route();
          } catch (error) {
            editor.prepend(message(error.message, true));
          }
        },
      }, "Uit plan halen")
    )
  );

  return h("div", { class: `session ${state}` },
    h("div", {
      class: "check",
      role: "img",
      "aria-label": session.completed ? "Gedaan" : session.partial ? "Te kort" : session.missed ? "Gemist" : "Nog te doen",
    }, session.completed ? "✓" : session.partial ? "~" : session.missed ? "×" : ""),
    h("div", {},
      h("strong", {}, session.title),
      h("span", { class: "muted" },
        ` · ${dayLabel(session.date, { weekday: "short", day: "numeric", month: "short" })}`,
        ` · ${SPORTS[session.sport]}`,
        details.length ? ` · ${details.join(" · ")}` : "")
    ),
    h("p", {}, session.description),
    session.actual && h("p", { class: `compliance ${session.compliance ?? ""}` }, complianceText(session)),
    h("div", { class: "session-actions" },
      h("button", {
        class: "link-button",
        type: "button",
        onclick: () => { editor.hidden = !editor.hidden; },
      }, "Aanpassen")
    ),
    editor
  );
}

function schedulePanel(plan) {
  return h("details", { class: "card form-toggle" },
    h("summary", {}, `Trainingsdagen aanpassen (nu ${plan.weekdays.length} per week)`),
    h("form", {
      onsubmit: submitter(async (form) => {
        const weekdays = pickedDays(form);

        if (weekdays.length < 2) throw new Error("Kies minstens twee dagen");

        if (!confirm("Je plan vanaf vandaag herschikken? Eigen aanpassingen aan komende trainingen gaan dan verloren.")) {
          return;
        }

        await api("/api/plans/active/schedule", {
          method: "PUT",
          json: { weekdays },
        });

        route();
      }),
    },
      weekdayPicker(plan.weekdays),
      h("p", { class: "muted", style: "margin:0" },
        "Wat al voorbij is, blijft staan. Alles vanaf vandaag wordt opnieuw ingepland, met de belangrijkste trainingen op je laatste dagen van de week."),
      h("div", {}, h("button", { class: "primary", type: "submit" }, "Plan herschikken"))
    )
  );
}

function calendarSubscription() {
  const address = `${location.origin}/api/calendar.ics`;
  const subscribe = address.replace(/^https:/, "webcals:").replace(/^http:/, "webcal:");
  const field = h("input", { value: address, readonly: true, "aria-label": "Adres van de agenda" });
  const copied = h("span", { class: "muted", "aria-live": "polite" });

  return h("section", { class: "card" },
    h("h2", {}, "Agenda-abonnement"),
    h("p", {}, "Abonneer je één keer: je plan blijft daarna vanzelf bijgewerkt in je agenda, ook als je het verandert."),
    h("div", { class: "row", style: "margin-bottom:10px" },
      h("a", { class: "button primary", href: subscribe }, art("calendar"), "Abonneer in Apple Agenda"),
      h("button", {
        class: "small",
        type: "button",
        onclick: async () => {
          field.select();

          try {
            await navigator.clipboard.writeText(address);
            copied.textContent = "Gekopieerd";
          } catch {
            copied.textContent = "Kopieer het adres hierboven zelf";
          }
        },
      }, "Kopieer adres"),
      copied
    ),
    field,
    h("details", {},
      h("summary", {}, "Hoe stel ik dit in?"),
      h("ul", { class: "highlights" },
        h("li", {}, h("b", {}, "iPhone: "), "ga naar Instellingen › Apps › Agenda › Agenda-accounts › Voeg account toe › Andere › Voeg agenda-abonnement toe, en plak het adres. De naam van de menu's kan per iOS-versie iets verschillen."),
        h("li", {}, h("b", {}, "Mac: "), "kies in Agenda Archief › Nieuw agenda-abonnement, plak het adres en kies als locatie Op mijn Mac, niet iCloud. Zet Vernieuwen automatisch op elk uur."),
        h("li", {}, h("b", {}, "Buitenshuis: "), "zet in de Tailscale-app VPN On Demand aan, anders kan je agenda de Pi niet bereiken en blijft hij de laatste versie tonen.")
      )
    )
  );
}

function weekSummary(week) {
  const parts = [
    PHASE_LABELS[week.phase],
    `${week.completed}/${week.total}`,
    week.planned_meters ? `${kilometers(week.done_meters)} van ${kilometers(week.planned_meters)}` : null,
  ].filter(Boolean);

  return ` · ${parts.join(" · ")}`;
}

function planPanel(plan) {
  const weeks = new Map();

  for (const session of plan.sessions) {
    if (!weeks.has(session.week)) weeks.set(session.week, []);
    weeks.get(session.week).push(session);
  }

  const today = localNow().slice(0, 10);

  // The week holding the next open session is the one that matters now.
  const nextOpen = plan.sessions.find((session) => !session.completed && session.date >= today)
    ?? plan.sessions.find((session) => !session.completed);
  const currentWeek = nextOpen?.week;

  return h("section", { class: "card" },
    h("div", { class: "row spread" },
      h("h2", { style: "margin:0" }, `Plan: ${plan.goal_name}`),
      h("span", { class: "muted" }, `${plan.completed} van ${plan.total} gedaan`)
    ),
    h("p", { class: "muted" },
      `${dayLabel(plan.start_date)} tot ${dayLabel(plan.end_date)}. Een training telt mee als je die sport in dezelfde week doet.`),
    xpBar(plan.completed, plan.total, "Voortgang van het plan"),
    plan.warning && h("div", { class: "message", style: "margin-top:12px" }, plan.warning),
    h("div", { style: "margin-top:12px" },
      [...weeks.entries()].map(([week, sessions]) =>
        h("details", { class: "week", open: week === currentWeek },
          h("summary", {},
            `Week ${week}`,
            weekSummary(plan.weeks.find((row) => row.week === week))),
          sessions.map(sessionRow)
        )
      )
    )
  );
}

export async function coachView() {
  const [plan, proposal, workouts, races] = await Promise.all([
    api("/api/plans/active"),
    api("/api/plans/proposal"),
    api("/api/workouts/?limit=1000"),
    api("/api/races/"),
  ]);

  const opening = plan
    ? plan.warning || `${PLAN_GOALS[plan.goal]}, hè. Goed. Doe wat er staat, niet wat je zin hebt. En als iets pijn doet, zeg je het.`
    : "Vertel me wat je wilt bereiken en hoe vaak je kunt komen. Ik doe een voorstel, en jij beslist wat er in je planning komt.";

  const dialog = coachDialog(opening);

  const ask = async (question) => {
    dialog.say("Effe nadenken...");

    try {
      const result = await api("/api/coach/ask", {
        json: { question },
      });

      dialog.say(result.answer);
    } catch (error) {
      dialog.say(`${error.message}\n\nJe plan werkt gewoon, alleen mijn praatjes niet.`);
    }
  };

  const presets = plan
    ? ["Leg mijn plan van deze week uit", "Hoe ver sta ik met mijn doel?", "Ben ik goed bezig?"]
    : ["Hoe ga ik de laatste weken?", "Wat moet ik eerst aanpakken?"];

  const planTab = [
    plan && planPanel(plan),
    plan && h("details", { class: "card form-toggle" },
      h("summary", {}, "Extra training toevoegen"),
      addSessionForm(localNow().slice(0, 10))
    ),
    plan && schedulePanel(plan),
    calendarSubscription(),
  ];

  const coachTab = [
    h("section", { class: "card" },
      h("h2", {}, "Vraag het de coach"),
      h("p", { class: "muted" },
        "Dit gebruikt het taalmodel op je laptop, dus die moet aanstaan. Een antwoord kan een minuut duren en kan fouten bevatten. Bij pijn of blessures ga je naar een arts of kinesist."),
      h("div", { class: "row", style: "margin-bottom:12px" },
        presets.map((preset) => h("button", {
          class: "small",
          type: "button",
          onclick: () => {
            dialog.element.scrollIntoView({ block: "center" });
            ask(preset);
          },
        }, preset))
      ),
      h("form", {
        onsubmit: submitter(async (form) => {
          dialog.element.scrollIntoView({ block: "center" });
          await ask(fields(form).question);
          form.reset();
        }),
      },
        h("label", {}, "Je vraag", h("textarea", {
          name: "question", rows: 2, maxlength: 1000, required: true,
        })),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Vraag stellen"))
      )
    ),
  ];

  return [
    h("h1", {}, "Plan"),
    dialog.element,
    subTabs("plan", [
      ...(plan ? [{ label: "Schema", content: planTab }] : []),
      { label: "Voorstel", content: proposalTab(proposal, races, Boolean(plan)) },
      { label: "Kalender", content: calendarPanel(plan, workouts, races) },
      { label: "Seizoen", content: seasonPanel(plan, races) },
      { label: "Coach", content: coachTab },
    ]),
  ];
}
