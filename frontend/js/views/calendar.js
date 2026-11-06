import { api } from "../api.js";
import { art } from "../art.js";
import { fields, h, message, number, submitter } from "../dom.js";
import { SPORTS, dayLabel, duration, isoDay, kilometers, lengthLabel } from "../format.js";
import { route } from "../navigation.js";

const SHOWN_WEEKS = 6;
const WEEK_NAMES = ["ma", "di", "wo", "do", "vr", "za", "zo"];

// Which week it opens on survives moving a training.
let weekOffset = 0;

function mondayOf(offset) {
  const today = new Date();
  const monday = new Date(today);

  monday.setHours(12, 0, 0, 0);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7) + offset * 7);

  return monday;
}

function sessionChip(session) {
  const details = [
    session.distance ? lengthLabel(session.distance) : null,
    session.duration ? duration(session.duration) : null,
  ].filter(Boolean).join(" · ");

  const state = session.completed ? "done" : session.partial ? "partial" : session.missed ? "missed" : "planned";

  return h("div", {
    class: `calendar-chip ${state}`,
    draggable: session.completed ? "false" : "true",
    title: `${session.title}${details ? ` · ${details}` : ""}`,
    "data-session": session.id,
    ondragstart: (event) => {
      event.dataTransfer.setData("text/plain", String(session.id));
      event.dataTransfer.effectAllowed = "move";
    },
  },
    art(`icon_${session.sport}`),
    h("span", {}, session.title)
  );
}

function workoutChip(workout) {
  const sport = workout.endurance_activity?.activity_type ?? "STRENGTH";
  const distance = workout.endurance_activity?.distance;

  return h("div", {
    class: "calendar-chip workout",
    title: `${SPORTS[sport]}${distance ? ` · ${kilometers(distance)}` : ""}`,
  },
    art(`icon_${sport}`),
    h("span", {}, distance ? kilometers(distance) : SPORTS[sport])
  );
}

const EXTRA_TITLES = {
  RUNNING: "Extra loop",
  CYCLING: "Extra rit",
  SWIMMING: "Extra zwembeurt",
  STRENGTH: "Extra krachttraining",
  OTHER: "Extra training",
};

// Also the way to add a training on a phone, where dragging does not work.
export function addSessionForm(initialDate) {
  return h("form", {
    class: "add-session",
    onsubmit: submitter(async (form) => {
      const values = fields(form);

      await api("/api/plans/sessions", {
        json: {
          date: values.date,
          sport: values.sport,
          title: values.title || EXTRA_TITLES[values.sport],
          distance: values.km ? Number(values.km) * 1000 : null,
          duration: values.minutes ? Math.round(number(values.minutes) * 60) : null,
        },
      });

      route();
    }),
  },
    h("div", { class: "fields" },
      h("label", {}, "Dag", h("input", { name: "date", type: "date", value: initialDate, required: true })),
      h("label", {}, "Sport",
        h("select", { name: "sport" },
          Object.entries(SPORTS).map(([key, label]) => h("option", { value: key }, label)))),
      h("label", {}, "Naam (optioneel)", h("input", { name: "title", maxlength: 100, placeholder: "Bijvoorbeeld rustige loop" })),
      h("label", {}, "Afstand (km)", h("input", { name: "km", type: "number", min: 0, step: "0.1", inputmode: "decimal" })),
      h("label", {}, "Duur (min)", h("input", { name: "minutes", type: "number", min: 0, inputmode: "numeric" }))
    ),
    h("div", {}, h("button", { class: "primary small", type: "submit" }, "Training toevoegen"))
  );
}

export function calendarPanel(plan, workouts, races) {
  const status = h("div", { "aria-live": "polite" });
  const adding = h("div", {});
  const grid = h("div", { class: "calendar" });
  const title = h("strong", {});

  const render = () => {
    const today = isoDay(new Date());
    const weekStart = isoDay(mondayOf(0));
    const first = mondayOf(weekOffset);
    const days = Array.from({ length: SHOWN_WEEKS * 7 }, (_, index) => {
      const day = new Date(first);
      day.setDate(first.getDate() + index);
      return day;
    });

    title.textContent = `${dayLabel(isoDay(days[0]), { day: "numeric", month: "short" })} tot ${dayLabel(isoDay(days.at(-1)))}`;

    const cells = days.map((day) => {
      const key = isoDay(day);
      const sessions = plan?.sessions.filter((session) => session.date === key) ?? [];
      const done = workouts.filter((workout) => workout.date.slice(0, 10) === key);
      const dayRaces = races.filter((race) => race.date === key);

      const cell = h("div", {
        class: `calendar-day${key === today ? " today" : ""}${key < today ? " past" : ""}`,
        "data-date": key,
        ondragover: (event) => {
          event.preventDefault();
          cell.classList.add("drop-target");
        },
        ondragleave: () => cell.classList.remove("drop-target"),
        ondrop: async (event) => {
          event.preventDefault();
          cell.classList.remove("drop-target");

          const id = event.dataTransfer.getData("text/plain");

          if (!id) return;

          try {
            await api(`/api/plans/sessions/${id}`, { method: "PATCH", json: { date: key } });
            route();
          } catch (error) {
            status.replaceChildren(message(error.message, true));
          }
        },
      },
        h("div", { class: "calendar-day-head" },
          h("span", { class: "calendar-date" }, String(day.getDate())),
          plan && key >= weekStart && h("button", {
            class: "calendar-add",
            type: "button",
            "aria-label": `Training toevoegen op ${dayLabel(key)}`,
            title: "Training toevoegen",
            onclick: () => {
              adding.replaceChildren(addSessionForm(key));
              adding.querySelector("select").focus();
            },
          }, "+")
        ),
        dayRaces.map((race) => h("div", { class: "calendar-chip race", title: `${race.name} (${race.priority})` }, h("span", {}, `${race.priority}: ${race.name}`))),
        sessions.map(sessionChip),
        done.map(workoutChip)
      );

      return cell;
    });

    grid.replaceChildren(
      ...WEEK_NAMES.map((name) => h("div", { class: "calendar-head" }, name)),
      ...cells
    );
  };

  const move = (delta) => {
    weekOffset = delta === 0 ? 0 : weekOffset + delta;
    render();
  };

  render();

  return h("section", { class: "card" },
    h("div", { class: "row spread", style: "margin-bottom:10px" },
      title,
      h("div", { class: "row" },
        h("button", { class: "small", type: "button", "aria-label": "Vorige weken", onclick: () => move(-SHOWN_WEEKS) }, "←"),
        h("button", { class: "small", type: "button", onclick: () => move(0) }, "Vandaag"),
        h("button", { class: "small", type: "button", "aria-label": "Volgende weken", onclick: () => move(SHOWN_WEEKS) }, "→")
      )
    ),
    status,
    h("div", { class: "calendar-scroll" }, grid),
    adding,
    h("p", { class: "muted", style: "margin:10px 0 0" },
      "Sleep een training naar een andere dag, of voeg er een toe met de +. Op een telefoon gebruik je Aanpassen en Extra training onder Schema.")
  );
}
