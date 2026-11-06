import { api } from "../api.js";
import { art } from "../art.js";
import { h, message } from "../dom.js";
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

export function calendarPanel(plan, workouts, races) {
  const status = h("div", { "aria-live": "polite" });
  const grid = h("div", { class: "calendar" });
  const title = h("strong", {});

  const render = () => {
    const today = isoDay(new Date());
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
        h("span", { class: "calendar-date" }, String(day.getDate())),
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
    h("p", { class: "muted", style: "margin:10px 0 0" },
      "Sleep een training naar een andere dag. Op een telefoon verplaats je ze via Aanpassen onder Schema.")
  );
}
