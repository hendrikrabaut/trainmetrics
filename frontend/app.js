"use strict";

const app = document.getElementById("app");
const SVG_NS = "http://www.w3.org/2000/svg";

let userId = null;

/* ---------- helpers ---------- */

// All text goes through textContent, so stored notes can never inject markup.
function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);

  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;

    if (key.startsWith("on")) element.addEventListener(key.slice(2), value);
    else if (key === "class") element.className = value;
    else if (key === "value") element.value = value;
    else if (value === true) element.setAttribute(key, "");
    else element.setAttribute(key, value);
  }

  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    element.append(child);
  }

  return element;
}

function svg(tag, attributes = {}) {
  const element = document.createElementNS(SVG_NS, tag);

  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }

  return element;
}

function errorText(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${item.loc.at(-1)}: ${item.msg}`)
      .join("; ");
  }

  return detail || "Er ging iets mis";
}

async function api(path, options = {}) {
  const init = { ...options };

  if (options.json !== undefined) {
    init.method = options.method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.json);
    delete init.json;
  }

  let response;

  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("De server is niet bereikbaar");
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) throw new Error(errorText(body?.detail));

  return body;
}

function number(value) {
  return value === "" || value === null || value === undefined ? null : Number(value);
}

function fields(form) {
  return Object.fromEntries(new FormData(form).entries());
}

const decimal = (value, digits = 1) =>
  value.toLocaleString("nl-BE", { maximumFractionDigits: digits });

const kilometers = (meters) => `${decimal(meters / 1000)} km`;

function duration(seconds) {
  if (!seconds) return "–";

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);

  return hours ? `${hours} u ${String(minutes).padStart(2, "0")}` : `${minutes} min`;
}

const dayLabel = (value, options = { day: "numeric", month: "short", year: "numeric" }) =>
  new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("nl-BE", options);

const shortDay = (value) => dayLabel(value, { day: "numeric", month: "short" });

function localNow() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

function pace(activity) {
  const speed = activity.average_speed;

  if (!speed) return null;

  const clock = (seconds) => {
    const whole = Math.round(seconds);
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  };

  if (activity.activity_type === "RUNNING") return `${clock(1000 / speed)} /km`;
  if (activity.activity_type === "SWIMMING") return `${clock(100 / speed)} /100 m`;

  return `${decimal(speed * 3.6)} km/u`;
}

const SPORTS = {
  RUNNING: "Lopen",
  CYCLING: "Fietsen",
  SWIMMING: "Zwemmen",
  OTHER: "Overig",
};

function message(text, isError = false) {
  return h("div", { class: `message${isError ? " error" : ""}`, role: "status" }, text);
}

// Runs a form submit and shows any error in the form instead of losing it.
function submitter(handler) {
  return async (event) => {
    event.preventDefault();

    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");

    form.querySelector(":scope > .message")?.remove();

    if (button) button.disabled = true;

    try {
      await handler(form);
    } catch (error) {
      form.prepend(message(error.message, true));
    } finally {
      if (button) button.disabled = false;
    }
  };
}

function table(columns, rows) {
  return h("div", { class: "table-wrap" },
    h("table", {},
      h("thead", {}, h("tr", {}, columns.map((column) => h("th", { scope: "col" }, column.label)))),
      h("tbody", {}, rows.map((row) =>
        h("tr", {}, columns.map((column) => h("td", {}, column.value(row))))
      ))
    )
  );
}

/* ---------- charts ---------- */

function niceMax(value) {
  if (value <= 0) return 2;

  const magnitude = 10 ** Math.floor(Math.log10(value));

  // Even steps only, so the middle gridline is a whole number too.
  for (const step of [2, 4, 6, 8, 10]) {
    if (value <= step * magnitude) return step * magnitude;
  }

  return 10 * magnitude;
}

// A figure with a title, a plot that redraws at its real width, and a table
// that gives the same values to anyone who cannot use the plot.
function chartFigure(title, rows, columns, draw) {
  const plot = h("div", { class: "chart" });
  const tooltip = h("div", { class: "tooltip", hidden: true });

  const figure = h("figure", {},
    h("figcaption", {}, title),
    plot,
    tooltip,
    h("details", {}, h("summary", {}, "Toon als tabel"), table(columns, rows))
  );

  const show = (x, y, value, label) => {
    tooltip.replaceChildren(h("strong", {}, value), label);
    tooltip.hidden = false;

    const left = Math.min(Math.max(x + 12, 0), plot.clientWidth - tooltip.offsetWidth);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${y + 24}px`;
  };

  const hide = () => { tooltip.hidden = true; };

  let drawnWidth = 0;

  new ResizeObserver(() => {
    const width = plot.clientWidth;

    if (width && width !== drawnWidth) {
      drawnWidth = width;
      plot.replaceChildren(draw(width, show, hide));
    }
  }).observe(plot);

  return figure;
}

const CHART = { height: 220, top: 10, right: 8, bottom: 26, left: 48 };

function yAxis(root, width, ticks, scale, format) {
  for (const tick of ticks) {
    const y = scale(tick);

    root.append(svg("line", {
      class: "grid", x1: CHART.left, x2: width - CHART.right, y1: y, y2: y,
    }));

    const label = svg("text", { x: CHART.left - 8, y: y + 4, "text-anchor": "end" });
    label.textContent = format(tick);
    root.append(label);
  }
}

function xLabel(root, x, text) {
  const label = svg("text", {
    x, y: CHART.height - 8, "text-anchor": "middle",
  });
  label.textContent = text;
  root.append(label);
}

function barChart(title, rows, { x, y, format, columns }) {
  const draw = (width, show, hide) => {
    const root = svg("svg", { height: CHART.height, role: "img", "aria-label": title });
    const plotWidth = width - CHART.left - CHART.right;
    const baseline = CHART.height - CHART.bottom;
    const max = niceMax(Math.max(...rows.map(y), 0));
    const scale = (value) => baseline - (value / max) * (baseline - CHART.top);
    const step = plotWidth / rows.length;
    const barWidth = Math.min(28, Math.max(4, step - 4));
    const labelEvery = Math.ceil(rows.length / Math.max(1, Math.floor(plotWidth / 64)));

    yAxis(root, width, [0, max / 2, max], scale, format);

    rows.forEach((row, index) => {
      const center = CHART.left + step * (index + 0.5);
      const value = y(row);

      if (value > 0) {
        const top = scale(value);
        const left = center - barWidth / 2;
        const right = center + barWidth / 2;
        const radius = Math.min(4, baseline - top, barWidth / 2);

        root.append(svg("path", {
          class: "bar",
          d: `M${left},${baseline} V${top + radius} Q${left},${top} ${left + radius},${top}`
            + ` H${right - radius} Q${right},${top} ${right},${top + radius} V${baseline} Z`,
        }));
      }

      if (index % labelEvery === 0) xLabel(root, center, x(row));

      const hit = svg("rect", {
        class: "hit",
        x: center - step / 2,
        y: CHART.top,
        width: step,
        height: baseline - CHART.top,
        tabindex: 0,
        "aria-label": `${x(row)}: ${format(value)}`,
      });

      const reveal = () => show(center, scale(value), format(value), `Week van ${x(row)}`);

      hit.addEventListener("pointerenter", reveal);
      hit.addEventListener("focus", reveal);
      hit.addEventListener("pointerleave", hide);
      hit.addEventListener("blur", hide);

      root.append(hit);
    });

    return root;
  };

  return chartFigure(title, rows, columns, draw);
}

function lineChart(title, rows, { x, y, format, columns }) {
  const draw = (width, show, hide) => {
    const root = svg("svg", { height: CHART.height, role: "img", "aria-label": title });
    const baseline = CHART.height - CHART.bottom;
    const times = rows.map((row) => new Date(`${x(row)}T12:00:00`).getTime());
    const values = rows.map(y);

    const first = times[0];
    const span = times.at(-1) - first;

    const left = CHART.left + 12;
    const right = width - CHART.right - 12;

    const xScale = (time) =>
      span ? left + ((time - first) / span) * (right - left) : (left + right) / 2;

    const low = Math.min(...values);
    const high = Math.max(...values);
    const padding = Math.max((high - low) * 0.15, Math.abs(high) * 0.02, 1);
    const yLow = Math.floor(low - padding);
    const yHigh = Math.ceil(high + padding);
    const yScale = (value) =>
      baseline - ((value - yLow) / (yHigh - yLow)) * (baseline - CHART.top);

    yAxis(root, width, [yLow, (yLow + yHigh) / 2, yHigh], yScale, format);

    const points = rows.map((row, index) => ({
      x: xScale(times[index]),
      y: yScale(values[index]),
      row,
    }));

    root.append(svg("path", {
      class: "line",
      d: points.map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`).join(" "),
    }));

    const crosshair = svg("line", {
      class: "crosshair", y1: CHART.top, y2: baseline, visibility: "hidden",
    });
    root.append(crosshair);

    const reveal = (point) => {
      crosshair.setAttribute("x1", point.x);
      crosshair.setAttribute("x2", point.x);
      crosshair.setAttribute("visibility", "visible");
      show(point.x, point.y, format(y(point.row)), dayLabel(x(point.row)));
    };

    const conceal = () => {
      crosshair.setAttribute("visibility", "hidden");
      hide();
    };

    // Labels at the two ends only; a time axis needs no more to be read.
    xLabel(root, points[0].x, shortDay(x(rows[0])));

    if (points.length > 1 && points.at(-1).x - points[0].x > 80) {
      xLabel(root, points.at(-1).x, shortDay(x(rows.at(-1))));
    }

    const hit = svg("rect", {
      class: "tracking-area",
      x: CHART.left,
      y: CHART.top,
      width: width - CHART.left - CHART.right,
      height: baseline - CHART.top,
    });

    hit.addEventListener("pointermove", (event) => {
      const bounds = root.getBoundingClientRect();
      const pointer = event.clientX - bounds.left;

      reveal(points.reduce((nearest, point) =>
        Math.abs(point.x - pointer) < Math.abs(nearest.x - pointer) ? point : nearest
      ));
    });
    hit.addEventListener("pointerleave", conceal);
    root.append(hit);

    for (const point of points) {
      const dot = svg("circle", {
        class: "point", cx: point.x, cy: point.y, r: 5, tabindex: 0,
        "aria-label": `${dayLabel(x(point.row))}: ${format(y(point.row))}`,
      });

      dot.addEventListener("focus", () => reveal(point));
      dot.addEventListener("blur", conceal);
      dot.style.pointerEvents = "none";

      root.append(dot);
    }

    return root;
  };

  return chartFigure(title, rows, columns, draw);
}

/* ---------- shared pieces ---------- */

function workoutCard(workout, onChange) {
  const activity = workout.endurance_activity;

  const heading = activity
    ? SPORTS[activity.activity_type]
    : workout.type === "STRENGTH" ? "Krachttraining" : "Duurtraining";

  const facts = [
    activity?.distance ? kilometers(activity.distance) : null,
    duration(activity?.duration || workout.duration),
    activity ? pace(activity) : null,
    activity?.average_heart_rate ? `${activity.average_heart_rate} bpm gem.` : null,
    activity?.elevation_gain ? `${decimal(activity.elevation_gain, 0)} hm` : null,
  ].filter((fact) => fact && fact !== "–");

  const remove = async () => {
    if (!confirm(`${heading} van ${dayLabel(workout.date)} verwijderen?`)) return;

    await api(`/api/workouts/${workout.id}`, { method: "DELETE" });
    onChange();
  };

  return h("article", { class: "card workout" },
    h("div", { class: "row spread" },
      h("div", {},
        h("h2", {}, heading),
        h("span", { class: "muted" }, dayLabel(workout.date))
      ),
      onChange && h("button", { class: "danger small", type: "button", onclick: remove }, "Verwijderen")
    ),
    facts.length > 0 && h("p", { style: "margin:8px 0 0" }, facts.join(" · ")),
    workout.exercises.length > 0 && h("ul", {},
      workout.exercises.map((item) =>
        h("li", {}, `${item.exercise.name}: `,
          item.sets.map((set) => `${set.weight ?? "–"} kg × ${set.reps ?? "–"}`).join(", "))
      )
    ),
    workout.notes && h("p", { class: "muted", style: "margin:8px 0 0" }, workout.notes)
  );
}

/* ---------- views ---------- */

async function overview() {
  const [weeks, workouts, weights] = await Promise.all([
    api(`/api/analytics/weekly?user_id=${userId}`),
    api("/api/workouts/?limit=5"),
    api(`/api/analytics/body-weight?user_id=${userId}`),
  ]);

  const week = weeks.at(-1);
  const meters = (row) => row.running_meters + row.cycling_meters + row.swimming_meters;

  const metrics = {
    workouts: {
      label: "Trainingen",
      y: (row) => row.workouts,
      format: (value) => decimal(value, 0),
    },
    distance: {
      label: "Afstand",
      y: (row) => meters(row) / 1000,
      format: (value) => `${decimal(value)} km`,
    },
    volume: {
      label: "Krachtvolume",
      y: (row) => row.strength_volume_kg,
      format: (value) => `${decimal(value, 0)} kg`,
    },
  };

  const slot = h("div", {});
  const buttons = h("div", { class: "row", style: "margin-bottom:12px" });

  const select = (key) => {
    const metric = metrics[key];

    buttons.querySelectorAll("button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.metric === key));
    });

    slot.replaceChildren(barChart(`${metric.label} per week`, weeks, {
      x: (row) => shortDay(row.week_start),
      y: metric.y,
      format: metric.format,
      columns: [
        { label: "Week van", value: (row) => dayLabel(row.week_start) },
        { label: metric.label, value: (row) => metric.format(metric.y(row)) },
      ],
    }));
  };

  for (const [key, metric] of Object.entries(metrics)) {
    buttons.append(h("button", {
      class: "small",
      type: "button",
      "data-metric": key,
      onclick: () => select(key),
    }, metric.label));
  }

  select("workouts");

  return [
    h("h1", {}, "Deze week"),
    h("div", { class: "tiles" },
      tile(decimal(week.workouts, 0), "trainingen"),
      tile(duration(week.duration_seconds), "trainingstijd"),
      tile(kilometers(meters(week)), "afstand"),
      tile(`${decimal(week.strength_volume_kg, 0)} kg`, "krachtvolume")
    ),
    h("section", { class: "card" }, buttons, slot),
    weights.length > 0 && h("section", { class: "card" }, weightChart(weights)),
    h("h2", {}, "Laatste trainingen"),
    workouts.length
      ? workouts.map((workout) => workoutCard(workout))
      : h("p", { class: "muted" }, "Nog geen trainingen. Voeg er een toe of importeer een bestand."),
  ];
}

function tile(value, label) {
  return h("div", { class: "tile" }, h("strong", {}, value), h("span", {}, label));
}

function weightChart(weights) {
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
    return h("p", {}, "Voeg eerst oefeningen toe onder ", h("a", { href: "#beheer" }, "Beheer"), ".");
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
          user_id: userId,
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
  return h("form", {
    onsubmit: submitter(async (form) => {
      const values = fields(form);
      const seconds = values.minutes ? Math.round(values.minutes * 60) : null;

      await api("/api/workouts/complete", {
        json: {
          user_id: userId,
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
          Object.entries(SPORTS).map(([key, label]) => h("option", { value: key }, label))
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

async function trainings() {
  const [workouts, exercises] = await Promise.all([
    api("/api/workouts/"),
    api("/api/exercises/"),
  ]);

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
    workouts.length
      ? workouts.map((workout) => workoutCard(workout, route))
      : h("p", { class: "muted" }, "Nog geen trainingen."),
  ];
}

function importView() {
  const results = h("div", { "aria-live": "polite" });

  return [
    h("h1", {}, "Activiteiten importeren"),
    h("section", { class: "card" },
      h("p", {}, "Upload FIT-, GPX- of TCX-bestanden. Een bestand dat je al importeerde, wordt overgeslagen."),
      h("p", { class: "muted" },
        "Polar: open de training in Polar Flow en exporteer als TCX. ",
        "Garmin: exporteer het origineel uit Garmin Connect (FIT)."),
      h("form", {
        onsubmit: submitter(async (form) => {
          results.replaceChildren();

          for (const file of form.elements.files.files) {
            const body = new FormData();
            body.append("file", file);

            try {
              const result = await api(`/api/import/?user_id=${userId}`, { method: "POST", body });
              const count = result.imported.length;

              results.append(message(
                `${file.name}: ${count} geïmporteerd${result.skipped ? `, ${result.skipped} overgeslagen` : ""}`
              ));
            } catch (error) {
              results.append(message(`${file.name}: ${error.message}`, true));
            }
          }

          form.reset();
        }),
      },
        h("label", {}, "Bestanden", h("input", {
          name: "files", type: "file", accept: ".fit,.gpx,.tcx", multiple: true, required: true,
        })),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Importeren"))
      )
    ),
    results,
  ];
}

async function progress() {
  const [exercises, records] = await Promise.all([
    api("/api/exercises/"),
    api(`/api/analytics/records?user_id=${userId}`),
  ]);

  if (!exercises.length) {
    return [
      h("h1", {}, "Progressie"),
      h("p", {}, "Voeg eerst oefeningen toe onder ", h("a", { href: "#beheer" }, "Beheer"), "."),
    ];
  }

  const slot = h("div", {});

  const show = async (exerciseId) => {
    const rows = await api(`/api/analytics/exercises/${exerciseId}/progress?user_id=${userId}`);
    const format = (value) => `${decimal(value)} kg`;

    slot.replaceChildren(rows.length
      ? lineChart("Geschat 1RM per trainingsdag", rows, {
        x: (row) => row.date,
        y: (row) => row.estimated_1rm_kg,
        format,
        columns: [
          { label: "Datum", value: (row) => dayLabel(row.date) },
          { label: "Geschat 1RM", value: (row) => format(row.estimated_1rm_kg) },
          { label: "Zwaarste set", value: (row) => format(row.top_weight_kg) },
          { label: "Volume", value: (row) => `${decimal(row.volume_kg, 0)} kg` },
        ],
      })
      : h("p", { class: "muted" }, "Nog geen sets voor deze oefening."));
  };

  // Open on an exercise that has data, so the page starts with a chart.
  const initial = records[0]?.exercise_id ?? exercises[0].id;

  await show(initial);

  return [
    h("h1", {}, "Progressie"),
    h("section", { class: "card" },
      h("label", { style: "margin-bottom:12px" }, "Oefening",
        h("select", {
          onchange: (event) => show(event.target.value).catch((error) => {
            slot.replaceChildren(message(error.message, true));
          }),
        }, exercises.map((exercise) => {
          const option = h("option", { value: exercise.id }, exercise.name);
          option.selected = exercise.id === initial;
          return option;
        }))
      ),
      slot
    ),
    h("section", { class: "card" },
      h("h2", {}, "Persoonlijke records"),
      records.length
        ? table([
          { label: "Oefening", value: (row) => row.exercise },
          { label: "Zwaarste set", value: (row) => `${decimal(row.top_weight_kg)} kg` },
          { label: "Op", value: (row) => dayLabel(row.top_weight_date) },
          { label: "Geschat 1RM", value: (row) => `${decimal(row.estimated_1rm_kg)} kg` },
          { label: "Op", value: (row) => dayLabel(row.estimated_1rm_date) },
        ], records)
        : h("p", { class: "muted" }, "Nog geen records."),
      h("p", { class: "muted", style: "margin:12px 0 0" },
        "Het geschatte 1RM gebruikt de Epley-formule: gewicht × (1 + herhalingen / 30).")
    ),
  ];
}

async function measurements() {
  const [rows, weights] = await Promise.all([
    api("/api/body-measurements/"),
    api(`/api/analytics/body-weight?user_id=${userId}`),
  ]);

  const value = (number, unit) => (number === null ? "–" : `${decimal(number)} ${unit}`);

  const remove = async (row) => {
    if (!confirm(`Meting van ${dayLabel(row.date)} verwijderen?`)) return;

    await api(`/api/body-measurements/${row.id}`, { method: "DELETE" });
    route();
  };

  return [
    h("h1", {}, "Metingen"),
    h("section", { class: "card" },
      h("h2", {}, "Nieuwe meting"),
      h("form", {
        onsubmit: submitter(async (form) => {
          const values = fields(form);

          await api("/api/body-measurements/", {
            json: {
              user_id: userId,
              date: values.date,
              weight: number(values.weight),
              body_fat: number(values.body_fat),
              waist: number(values.waist),
              chest: number(values.chest),
            },
          });

          route();
        }),
      },
        h("div", { class: "fields" },
          h("label", {}, "Datum", h("input", {
            name: "date", type: "date", value: localNow().slice(0, 10), required: true,
          })),
          h("label", {}, "Gewicht (kg)", h("input", { name: "weight", type: "number", min: 0, step: "0.1", inputmode: "decimal" })),
          h("label", {}, "Vetpercentage", h("input", { name: "body_fat", type: "number", min: 0, step: "0.1", inputmode: "decimal" })),
          h("label", {}, "Taille (cm)", h("input", { name: "waist", type: "number", min: 0, step: "0.1", inputmode: "decimal" })),
          h("label", {}, "Borst (cm)", h("input", { name: "chest", type: "number", min: 0, step: "0.1", inputmode: "decimal" }))
        ),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Meting opslaan"))
      )
    ),
    weights.length > 0 && h("section", { class: "card" }, weightChart(weights)),
    rows.length > 0 && h("section", { class: "card" },
      table([
        { label: "Datum", value: (row) => dayLabel(row.date) },
        { label: "Gewicht", value: (row) => value(row.weight, "kg") },
        { label: "Vet", value: (row) => value(row.body_fat, "%") },
        { label: "Taille", value: (row) => value(row.waist, "cm") },
        { label: "Borst", value: (row) => value(row.chest, "cm") },
        {
          label: "",
          value: (row) => h("button", {
            class: "danger small", type: "button", onclick: () => remove(row),
          }, "Verwijderen"),
        },
      ], rows)
    ),
  ];
}

async function management() {
  const [exercises, equipment] = await Promise.all([
    api("/api/exercises/"),
    api("/api/equipment/"),
  ]);

  const failure = h("div", { "aria-live": "polite" });

  const attempt = async (action) => {
    failure.replaceChildren();

    try {
      await action();
      route();
    } catch (error) {
      failure.replaceChildren(message(error.message, true));
    }
  };

  return [
    h("h1", {}, "Beheer"),
    failure,
    h("section", { class: "card" },
      h("h2", {}, "Oefeningen"),
      h("form", {
        onsubmit: submitter(async (form) => {
          const values = fields(form);

          await api("/api/exercises/", {
            json: { name: values.name, category: values.category || null },
          });

          route();
        }),
      },
        h("div", { class: "fields" },
          h("label", {}, "Naam", h("input", { name: "name", required: true })),
          h("label", {}, "Categorie", h("input", { name: "category", placeholder: "Chest, Back…" }))
        ),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Oefening toevoegen"))
      ),
      exercises.length > 0 && h("div", { style: "margin-top:16px" }, table([
        { label: "Naam", value: (row) => row.name },
        { label: "Categorie", value: (row) => row.category || "–" },
        {
          label: "",
          value: (row) => h("button", {
            class: "danger small",
            type: "button",
            onclick: () => confirm(`${row.name} verwijderen?`)
              && attempt(() => api(`/api/exercises/${row.id}`, { method: "DELETE" })),
          }, "Verwijderen"),
        },
      ], exercises))
    ),
    h("section", { class: "card" },
      h("h2", {}, "Materiaal"),
      h("form", {
        onsubmit: submitter(async (form) => {
          const values = fields(form);

          await api("/api/equipment/", {
            json: {
              user_id: userId,
              name: values.name,
              category: values.category || null,
              brand: values.brand || null,
              model: values.model || null,
            },
          });

          route();
        }),
      },
        h("div", { class: "fields" },
          h("label", {}, "Naam", h("input", { name: "name", required: true })),
          h("label", {}, "Categorie", h("input", { name: "category", placeholder: "BIKE, WEARABLE…" })),
          h("label", {}, "Merk", h("input", { name: "brand" })),
          h("label", {}, "Model", h("input", { name: "model" }))
        ),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Materiaal toevoegen"))
      ),
      equipment.length > 0 && h("div", { style: "margin-top:16px" }, table([
        {
          label: "Materiaal",
          value: (row) => h("div", {},
            row.name,
            h("div", { class: "muted" },
              [row.category, row.status === "ACTIVE" ? "In gebruik" : "Afgevoerd"]
                .filter(Boolean)
                .join(" · "))
          ),
        },
        {
          label: "",
          value: (row) => h("div", { class: "row" },
            h("button", {
              class: "small",
              type: "button",
              onclick: () => attempt(() => api(`/api/equipment/${row.id}`, {
                method: "PATCH",
                json: { status: row.status === "ACTIVE" ? "RETIRED" : "ACTIVE" },
              })),
            }, row.status === "ACTIVE" ? "Afvoeren" : "Terugzetten"),
            h("button", {
              class: "danger small",
              type: "button",
              onclick: () => confirm(`${row.name} verwijderen?`)
                && attempt(() => api(`/api/equipment/${row.id}`, { method: "DELETE" })),
            }, "Verwijderen")
          ),
        },
      ], equipment))
    ),
  ];
}

function coachView() {
  const output = h("div", { "aria-live": "polite" });

  return [
    h("h1", {}, "Coach"),
    h("section", { class: "card" },
      h("p", {}, "De coach draait op je eigen laptop, dus je gegevens blijven thuis. De laptop moet aanstaan, en een antwoord kan een minuut duren."),
      h("form", {
        onsubmit: submitter(async (form) => {
          output.replaceChildren(message("De coach denkt na…"));

          try {
            const result = await api("/api/coach/ask", {
              json: { user_id: userId, question: fields(form).question },
            });

            output.replaceChildren(h("section", { class: "card answer" }, result.answer));
          } catch (error) {
            output.replaceChildren(message(error.message, true));
          }
        }),
      },
        h("label", {}, "Je vraag", h("textarea", {
          name: "question",
          rows: 3,
          maxlength: 1000,
          required: true,
          placeholder: "Hoeveel heb ik de afgelopen weken gelopen?",
        })),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Vraag stellen"))
      )
    ),
    output,
    h("p", { class: "muted" }, "Een taalmodel kan fouten maken. Controleer belangrijke cijfers, en vraag bij blessures een arts of kinesist om advies."),
  ];
}

function setupView() {
  return [
    h("h1", {}, "Welkom bij TrainMetrics"),
    h("section", { class: "card" },
      h("form", {
        onsubmit: submitter(async (form) => {
          const created = await api("/api/users/", { json: fields(form) });
          userId = created.id;
          location.hash = "#overzicht";
          route();
        }),
      },
        h("p", {}, "Maak eerst je profiel aan."),
        h("div", { class: "fields" },
          h("label", {}, "Naam", h("input", { name: "name", required: true })),
          h("label", {}, "E-mail", h("input", { name: "email", type: "email", required: true }))
        ),
        h("div", {}, h("button", { class: "primary", type: "submit" }, "Beginnen"))
      )
    ),
  ];
}

/* ---------- routing ---------- */

const VIEWS = {
  overzicht: overview,
  trainingen: trainings,
  import: importView,
  progressie: progress,
  metingen: measurements,
  beheer: management,
  coach: coachView,
};

let routeCounter = 0;

async function route() {
  const current = ++routeCounter;
  const name = location.hash.slice(1);
  const view = VIEWS[name] ? name : "overzicht";

  document.querySelectorAll(".site-header nav a").forEach((link) => {
    if (link.getAttribute("href") === `#${view}`) {
      link.setAttribute("aria-current", "page");
      link.scrollIntoView({ block: "nearest", inline: "nearest" });
    } else {
      link.removeAttribute("aria-current");
    }
  });

  try {
    if (userId === null) {
      const users = await api("/api/users/");

      if (!users.length) {
        app.replaceChildren(...setupView());
        return;
      }

      userId = users[0].id;
    }

    const content = await VIEWS[view]();

    // A slower earlier view must not overwrite the page the user went to.
    if (current === routeCounter) {
      app.replaceChildren(...[content].flat().flat().filter(Boolean));
    }
  } catch (error) {
    if (current === routeCounter) app.replaceChildren(message(error.message, true));
  }
}

window.addEventListener("hashchange", route);
route();
