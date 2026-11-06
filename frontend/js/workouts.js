import { segmentTool, workoutDetail } from "./views/workout-detail.js";
import { api } from "./api.js";
import { art, drawRoutes } from "./art.js";
import { lineChart } from "./charts.js";
import { fields, h, message, submitter } from "./dom.js";
import { SPORTS, dayLabel, decimal, duration, kilometers, pace } from "./format.js";
import { game } from "./gamification.js";
import { route } from "./navigation.js";

export function workoutSport(workout) {
  return workout.endurance_activity?.activity_type ?? "STRENGTH";
}

// For when a device got it wrong, such as GPS while swimming in open water.
function distanceEditor(workout) {
  return h("form", {
    class: "distance-edit",
    onsubmit: submitter(async (form) => {
      const km = fields(form).km;

      await api(`/api/workouts/${workout.id}/endurance`, {
        method: "PATCH",
        json: { distance: km ? Number(km) * 1000 : null },
      });

      route();
    }),
  },
    h("label", {}, "Afstand aanpassen (km)", h("input", {
      name: "km", type: "number", min: 0, step: "0.01", inputmode: "decimal",
      value: workout.endurance_activity.distance
        ? String(Math.round(workout.endurance_activity.distance / 10) / 100)
        : "",
    })),
    h("button", { class: "small", type: "submit" }, "Opslaan")
  );
}

// Asks first, because the map tiles tell OpenStreetMap which area you look at.
function routeButton(workout) {
  const holder = h("div", {});

  const show = async () => {
    const element = h("div", { class: "route-map" });
    holder.replaceChildren(element);

    try {
      const route = await api(`/api/workouts/${workout.id}/route`);
      const map = await drawRoutes(element, [{ points: route.points }], { markEnds: true });
      holder.append(segmentTool(map, workout, window.L));
    } catch (error) {
      holder.replaceChildren(message(error.message, true));
    }
  };

  holder.append(h("button", {
    class: "small",
    type: "button",
    style: "margin-bottom:10px",
    onclick: show,
  }, art("map"), "Toon route op kaart"));

  return holder;
}

export function workoutRow(workout, onChange) {
  const activity = workout.endurance_activity;
  const sport = workoutSport(workout);

  const facts = [
    dayLabel(workout.date, { weekday: "short", day: "numeric", month: "short" }),
    activity?.distance ? kilometers(activity.distance) : null,
    duration(activity?.duration || workout.duration),
    activity ? pace(activity) : null,
  ].filter((fact) => fact && fact !== "–");

  const details = [
    activity?.average_heart_rate ? `${activity.average_heart_rate} bpm gemiddeld` : null,
    activity?.max_heart_rate ? `${activity.max_heart_rate} bpm maximaal` : null,
    activity?.elevation_gain ? `${decimal(activity.elevation_gain, 0)} hoogtemeters` : null,
    activity?.calories ? `${decimal(activity.calories, 0)} kcal` : null,
    activity?.running_index ? `Running Index ${activity.running_index}` : null,
  ].filter(Boolean);

  const remove = async () => {
    if (!confirm(`${SPORTS[sport]} van ${dayLabel(workout.date)} verwijderen? De XP ervan gaat ook weg.`)) return;

    await api(`/api/workouts/${workout.id}`, { method: "DELETE" });
    onChange();
  };

  const xp = game?.workout_xp[workout.id];

  const extra = h("div", { class: "workout-extra" });
  let loaded = false;

  return h("details", {
    class: "workout-row",
    ontoggle: async (event) => {
      if (!event.currentTarget.open || loaded) return;

      loaded = true;

      try {
        extra.replaceChildren(...await workoutDetail(workout));
      } catch (error) {
        extra.replaceChildren(message(error.message, true));
      }
    },
  },
    h("summary", {},
      h("span", { class: `sport-mark ${sport}`, "aria-hidden": "true" }, art(`icon_${sport}`)),
      h("span", {},
        h("span", { class: "workout-title" }, SPORTS[sport]),
        h("span", { class: "workout-facts" }, facts.join(" · "))
      ),
      xp && h("span", { class: "xp-gain" }, `+${xp} XP`)
    ),
    h("div", { class: "workout-body" },
      details.length > 0 && h("p", {}, details.join(" · ")),
      workout.has_route && routeButton(workout),
      extra,
      workout.exercises.length > 0 && h("ul", {},
        workout.exercises.map((item) =>
          h("li", {}, `${item.exercise.name}: `,
            item.sets.map((set) => `${set.weight ?? "–"} kg × ${set.reps ?? "–"}`).join(", "))
        )
      ),
      workout.notes && h("p", { class: "muted" }, workout.notes),
      onChange && activity && distanceEditor(workout),
      onChange && h("button", { class: "danger small", type: "button", onclick: remove }, "Verwijderen")
    )
  );
}

export function weightChart(weights) {
  const format = (value) => `${decimal(value)} kg`;

  return lineChart("Lichaamsgewicht", weights, {
    x: (row) => row.date,
    y: (row) => row.weight_kg,
    format,
    columns: [
      { label: "Datum", value: (row) => dayLabel(row.date) },
      { label: "Gewicht", value: (row) => format(row.weight_kg) },
    ],
  });
}
