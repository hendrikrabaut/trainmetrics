import { api } from "../api.js";
import { fields, h, number, submitter } from "../dom.js";
import { SPORTS, dayLabel, localNow } from "../format.js";
import { route } from "../navigation.js";
import { workoutRow, workoutSport } from "../workouts.js";

function setRow(onRemove) {
  const row = h("div", { class: "set-row" },
    h("span", { class: "muted set-number" }),
    h("label", {}, "kg", h("input", {
      class: "set-weight", type: "number", min: 0, step: "0.25", inputmode: "decimal",
    })),
    h("label", {}, "herhalingen", h("input", {
      class: "set-reps", type: "number", min: 0, step: 1, inputmode: "numeric", required: true,
    })),
    h("button", {
      class: "small", type: "button", "aria-label": "Set verwijderen",
      onclick: () => { row.remove(); onRemove(); },
    }, "×")
  );

  return row;
}

function exerciseBlock(exercises) {
  const sets = h("div", {});

  const renumber = () => {
    sets.querySelectorAll(".set-number").forEach((label, index) => {
      label.textContent = `${index + 1}.`;
    });
  };

  const addSet = () => {
    const previous = sets.querySelector(".set-row:last-child");
    const row = setRow(renumber);

    // The next set is usually the same weight, so start from the previous one.
    if (previous) {
      row.querySelector(".set-weight").value = previous.querySelector(".set-weight").value;
      row.querySelector(".set-reps").value = previous.querySelector(".set-reps").value;
    }

    sets.append(row);
    renumber();
  };

  addSet();

  const block = h("div", { class: "exercise-block" },
    h("div", { class: "row spread" },
      h("label", { style: "flex:1" }, "Oefening",
        h("select", { class: "exercise-id", required: true },
          exercises.map((exercise) => h("option", { value: exercise.id }, exercise.name))
        )
      ),
      h("button", {
        class: "danger small", type: "button", onclick: () => block.remove(),
      }, "Oefening weg")
    ),
    sets,
    h("div", {}, h("button", { class: "small", type: "button", onclick: addSet }, "Set toevoegen"))
  );

  return block;
}

function strengthForm(exercises, onSaved) {
  if (!exercises.length) {
    return h("p", {}, "Voeg eerst oefeningen toe onder ", h("a", { href: "#profiel" }, "Profiel"), ".");
  }

  const blocks = h("div", { style: "display:grid;gap:12px" }, exerciseBlock(exercises));

  return h("form", {
    onsubmit: submitter(async (form) => {
      const values = fields(form);

      const items = [...blocks.querySelectorAll(".exercise-block")].map((block, index) => ({
        exercise_id: Number(block.querySelector(".exercise-id").value),
        exercise_order: index + 1,
        sets: [...block.querySelectorAll(".set-row")].map((row, setIndex) => ({
          set_number: setIndex + 1,
          weight: number(row.querySelector(".set-weight").value),
          reps: number(row.querySelector(".set-reps").value),
        })),
      }));

      await api("/api/workouts/complete", {
        json: {
          type: "STRENGTH",
          date: values.date,
          duration: values.minutes ? Math.round(values.minutes * 60) : null,
          notes: values.notes || null,
          exercises: items,
        },
      });

      onSaved();
    }),
  },
    h("div", { class: "fields" },
      h("label", {}, "Datum", h("input", { name: "date", type: "datetime-local", value: localNow(), required: true })),
      h("label", {}, "Duur (min)", h("input", { name: "minutes", type: "number", min: 0, inputmode: "numeric" }))
    ),
    blocks,
    h("div", {}, h("button", {
      class: "small", type: "button",
      onclick: () => blocks.append(exerciseBlock(exercises)),
    }, "Oefening toevoegen")),
    h("label", {}, "Notities", h("textarea", { name: "notes", rows: 2 })),
    h("div", {}, h("button", { class: "primary", type: "submit" }, "Training opslaan"))
  );
}

function enduranceForm(onSaved) {
  const sports = Object.entries(SPORTS).filter(([key]) => key !== "STRENGTH");

  return h("form", {
    onsubmit: submitter(async (form) => {
      const values = fields(form);
      const seconds = values.minutes ? Math.round(values.minutes * 60) : null;

      await api("/api/workouts/complete", {
        json: {
          type: "ENDURANCE",
          date: values.date,
          duration: seconds,
          notes: values.notes || null,
          endurance_activity: {
            activity_type: values.sport,
            distance: values.km ? values.km * 1000 : null,
            duration: seconds,
            average_heart_rate: number(values.hr),
            max_heart_rate: number(values.max_hr),
            elevation_gain: number(values.ascent),
            calories: number(values.calories),
          },
        },
      });

      onSaved();
    }),
  },
    h("div", { class: "fields" },
      h("label", {}, "Sport",
        h("select", { name: "sport" },
          sports.map(([key, label]) => h("option", { value: key }, label))
        )
      ),
      h("label", {}, "Datum", h("input", { name: "date", type: "datetime-local", value: localNow(), required: true })),
      h("label", {}, "Afstand (km)", h("input", { name: "km", type: "number", min: 0, step: "0.01", inputmode: "decimal" })),
      h("label", {}, "Duur (min)", h("input", { name: "minutes", type: "number", min: 0, step: "0.1", inputmode: "decimal" })),
      h("label", {}, "Gem. hartslag", h("input", { name: "hr", type: "number", min: 1, max: 260, inputmode: "numeric" })),
      h("label", {}, "Max. hartslag", h("input", { name: "max_hr", type: "number", min: 1, max: 260, inputmode: "numeric" })),
      h("label", {}, "Hoogtemeters", h("input", { name: "ascent", type: "number", min: 0, inputmode: "numeric" })),
      h("label", {}, "Calorieën", h("input", { name: "calories", type: "number", min: 0, inputmode: "numeric" }))
    ),
    h("label", {}, "Notities", h("textarea", { name: "notes", rows: 2 })),
    h("div", {}, h("button", { class: "primary", type: "submit" }, "Training opslaan"))
  );
}

export async function trainings() {
  const [workouts, exercises] = await Promise.all([
    api("/api/workouts/?limit=1000"),
    api("/api/exercises/"),
  ]);

  const list = h("div", {});
  const filters = h("div", { class: "row", style: "margin-bottom:4px" });

  const show = (sport) => {
    filters.querySelectorAll("button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.sport === sport));
    });

    const shown = workouts.filter((workout) => sport === "ALL" || workoutSport(workout) === sport);
    const months = new Map();

    for (const workout of shown) {
      const month = dayLabel(workout.date, { month: "long", year: "numeric" });
      if (!months.has(month)) months.set(month, []);
      months.get(month).push(workout);
    }

    list.replaceChildren(...(shown.length
      ? [...months.entries()].flatMap(([month, rows]) => [
        h("h2", { class: "month" }, month),
        h("div", { class: "workout-list" }, rows.map((workout) => workoutRow(workout, route))),
      ])
      : [h("p", { class: "muted", style: "margin-top:16px" }, "Geen trainingen gevonden.")]));
  };

  // Only sports that actually occur, so no filter leads to an empty page.
  const present = new Set(workouts.map(workoutSport));
  const options = [["ALL", "Alles"], ...Object.entries(SPORTS).filter(([key]) => present.has(key))];

  for (const [key, label] of options) {
    filters.append(h("button", {
      class: "small", type: "button", "data-sport": key, onclick: () => show(key),
    }, label));
  }

  show("ALL");

  return [
    h("h1", {}, "Trainingen"),
    h("details", { class: "card form-toggle" },
      h("summary", {}, "Krachttraining toevoegen"),
      strengthForm(exercises, route)
    ),
    h("details", { class: "card form-toggle" },
      h("summary", {}, "Duurtraining toevoegen"),
      enduranceForm(route)
    ),
    workouts.length > 0 && filters,
    list,
  ];
}
