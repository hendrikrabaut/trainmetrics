"use strict";

const app = document.getElementById("app");
const SVG_NS = "http://www.w3.org/2000/svg";

let userId = null;
let game = null;

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

const percentage = (part, whole) => `${Math.min(100, (part / whole) * 100)}%`;

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

function clock(seconds) {
  const whole = Math.round(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = String(whole % 60).padStart(2, "0");

  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${rest}`
    : `${minutes}:${rest}`;
}

const SPORTS = {
  RUNNING: "Lopen",
  CYCLING: "Fietsen",
  SWIMMING: "Zwemmen",
  OTHER: "Overig",
  STRENGTH: "Kracht",
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
          style: `--i:${index}`,
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
    // Values that cannot go negative should not get an axis below zero.
    const yLow = low >= 0 ? Math.max(0, Math.floor(low - padding)) : Math.floor(low - padding);
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
      pathLength: 1,
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

    // A daily series would be a wall of dots. Its table holds every value.
    for (const point of points.length <= 40 ? points : []) {
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

/* ---------- game layer ---------- */

function xpBar(part, whole, label) {
  return h("div", {
    class: "xp-bar",
    role: "progressbar",
    "aria-valuemin": 0,
    "aria-valuemax": whole,
    "aria-valuenow": part,
    "aria-label": label,
  }, h("div", {
    class: "xp-fill",
    style: `width:${percentage(part, whole)}`,
  }));
}

function playerPanel() {
  const total = h("span", { class: "level-total" });
  countUp(total, game.xp, (value) => `${decimal(value, 0)} XP`);

  return h("section", { class: "card level-card" },
    h("div", { class: "row spread" },
      h("div", {},
        h("span", { class: "level-number" }, `Level ${game.level}`),
        h("span", { class: "level-title" }, game.title)
      ),
      total
    ),
    xpBar(game.xp_into_level, game.xp_for_next_level, "Voortgang naar het volgende level"),
    h("div", { class: "row spread" },
      h("span", { class: "muted" },
        `Nog ${decimal(game.xp_for_next_level - game.xp_into_level, 0)} XP tot level ${game.level + 1}`),
      h("span", { class: "muted" },
        game.streak_weeks > 0 && art("flame"),
        game.streak_weeks === 1 ? "1 week op rij" : `${game.streak_weeks} weken op rij`)
    )
  );
}

function questPanel() {
  return h("section", { class: "card" },
    h("h2", {}, "Quests van deze week"),
    h("div", { class: "quest-list" }, game.quests.map((quest) =>
      h("div", { class: `quest${quest.completed ? " done" : ""}` },
        h("div", { class: "row spread" },
          h("h3", {}, quest.name),
          h("span", { class: "xp-gain" }, `+${quest.xp} XP`)
        ),
        h("p", { class: "muted", style: "margin:0 0 4px" },
          `${quest.description} (${quest.progress} van ${quest.target})`),
        xpBar(quest.progress, quest.target, quest.name)
      )
    ))
  );
}

function coachLine(next, estimate) {
  const open = game.quests.find((quest) => !quest.completed);
  const form = estimate.fitness?.form;

  if (game.xp === 0) {
    return "Dus jij wilt trainen. Dat zeggen ze allemaal. Laat maar zien: één training, dan praten we verder.";
  }

  if (!next) {
    return "Zonder plan ben je gewoon wat aan het rondlopen, jong. Kom naar mijn hoek, dan maken we er een.";
  }

  if (form !== undefined && form < -10) {
    return "Je zit diep. Rustig trainen is ook trainen, dus laat je ego thuis.";
  }

  if (form !== undefined && form > 5) {
    return "Je bent fris. Dan heb je ook geen excuus, hè.";
  }

  if (open) return `Doe wat er staat, niet onderhandelen. En die quest "${open.name}" staat er nog.`;

  return "Alle quests binnen deze week. Niet slecht. Niet naast je schoenen gaan lopen.";
}

function showLevelUp(level, title) {
  const close = () => dialog.close();

  confetti();

  const dialog = h("dialog", { class: "level-up", onclose: () => dialog.remove() },
    art("party"),
    art("coach"),
    h("h2", {}, `Level ${level}!`),
    h("p", {}, `Je bent nu: ${title}. Niet naast je schoenen gaan lopen.`),
    h("button", { class: "primary", type: "button", onclick: close }, "Terug aan het werk")
  );

  document.body.append(dialog);
  dialog.showModal();
}

function showToast(text) {
  const toast = h("div", { class: "toast" }, text);
  document.getElementById("toasts").append(toast);
  setTimeout(() => toast.remove(), 2800);
}

function showXpToast(amount) {
  showToast(`+${amount} XP`);
}

// Loads the score and celebrates anything gained since the last look.
async function refreshGame() {
  const previous = game;

  game = await api(`/api/game/profile?user_id=${userId}`);

  const chip = document.getElementById("level-chip");
  chip.textContent = `Lv ${game.level}`;
  chip.hidden = false;

  if (!previous) return;

  if (game.xp > previous.xp) showXpToast(game.xp - previous.xp);

  const had = new Set(previous.badges.filter((badge) => badge.earned_on).map((badge) => badge.id));
  const newBadges = game.badges.filter((badge) => badge.earned_on && !had.has(badge.id));

  if (newBadges.length > 3) showToast(`${newBadges.length} nieuwe badges!`);
  else for (const badge of newBadges) showToast(`Nieuwe badge: ${badge.name}`);

  if (game.level > previous.level) showLevelUp(game.level, game.title);
  else if (newBadges.length) confetti(45);
}

function medal(earned) {
  return picture("medal", `medal${earned ? " earned" : ""}`);
}

/* ---------- shared pieces ---------- */

function workoutSport(workout) {
  return workout.endurance_activity?.activity_type ?? "STRENGTH";
}

function workoutRow(workout, onChange) {
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

  return h("details", { class: "workout-row" },
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
      workout.exercises.length > 0 && h("ul", {},
        workout.exercises.map((item) =>
          h("li", {}, `${item.exercise.name}: `,
            item.sets.map((set) => `${set.weight ?? "–"} kg × ${set.reps ?? "–"}`).join(", "))
        )
      ),
      workout.notes && h("p", { class: "muted" }, workout.notes),
      onChange && h("button", { class: "danger small", type: "button", onclick: remove }, "Verwijderen")
    )
  );
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

function tile(value, label) {
  return h("div", { class: "tile" }, h("strong", {}, value), h("span", {}, label));
}

/* ---------- today ---------- */

function isoDay(date) {
  const local = new Date(date);
  local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
  return local.toISOString().slice(0, 10);
}

function weekDays() {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));

  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(monday);
    day.setDate(monday.getDate() + index);
    return day;
  });
}

function nextSession(plan) {
  const today = localNow().slice(0, 10);

  return plan?.sessions.find((session) => !session.completed && session.date >= today) ?? null;
}

function whenLabel(date) {
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  if (date === isoDay(today)) return "Vandaag";
  if (date === isoDay(tomorrow)) return "Morgen";

  return dayLabel(date, { weekday: "long", day: "numeric", month: "long" });
}

function heroPanel(next, estimate) {
  const coach = coachDialog(coachLine(next, estimate)).element;

  if (!next) {
    return h("section", { class: "hero" },
      h("div", { class: "hero-top" },
        h("div", {},
          h("span", { class: "eyebrow" }, "Volgende training"),
          h("h2", {}, "Nog niets gepland"),
          h("p", { class: "description" }, "Kies een doel en je dagen, en je krijgt een schema op maat van wat je nu aankunt."),
          h("a", { class: "button primary", href: "#plan" }, "Maak een plan")
        ),
        art("RUNNING")
      ),
      coach
    );
  }

  const facts = [
    SPORTS[next.sport],
    next.distance ? kilometers(next.distance) : null,
    next.duration ? duration(next.duration) : null,
  ].filter(Boolean);

  return h("section", { class: "hero" },
    h("div", { class: "hero-top" },
      h("div", {},
        h("span", { class: "eyebrow" }, `Volgende training · ${whenLabel(next.date)}`),
        h("h2", {}, next.title),
        h("p", { class: "facts" }, facts.join(" · ")),
        h("p", { class: "description" }, next.description),
        h("a", { class: "button primary", href: "#plan" }, "Bekijk je plan")
      ),
      art(next.sport)
    ),
    coach
  );
}

function weekPanel(plan, workouts) {
  const today = isoDay(new Date());
  const sessions = plan?.sessions ?? [];
  const days = weekDays();
  const inWeek = new Set(days.map(isoDay));

  const trained = workouts.filter((workout) => inWeek.has(workout.date.slice(0, 10)));
  const planned = sessions.filter((session) => inWeek.has(session.date));

  return h("section", { class: "card" },
    h("div", { class: "row spread" },
      h("h2", { style: "margin:0" }, "Deze week"),
      h("span", { class: "muted" }, planned.length
        ? `${planned.filter((session) => session.completed).length} van ${planned.length} gepland gedaan`
        : `${trained.length} ${trained.length === 1 ? "training" : "trainingen"}`)
    ),
    h("div", { class: "week-strip", style: "margin-top:12px" }, days.map((day) => {
      const key = isoDay(day);
      const done = trained.filter((workout) => workout.date.slice(0, 10) === key);
      const todo = planned.filter((session) => session.date === key && !session.completed);

      const label = [
        dayLabel(key, { weekday: "long", day: "numeric", month: "long" }),
        ...done.map((workout) => `gedaan: ${SPORTS[workoutSport(workout)]}`),
        ...todo.map((session) => `gepland: ${session.title}`),
      ].join(", ");

      return h("div", {
        class: `week-day${key === today ? " today" : ""}`,
        role: "img",
        "aria-label": label,
        title: label,
      },
        dayLabel(key, { weekday: "short" }).replace(".", ""),
        h("b", {}, String(day.getDate())),
        h("div", { class: `week-mark${done.length ? " done" : todo.length ? " planned" : ""}` }, done.length ? "✓" : "")
      );
    })),
    h("div", { class: "week-legend muted" },
      h("span", {}, "✓ getraind"),
      h("span", {}, "○ gepland")
    )
  );
}

async function overview() {
  const [workouts, plan, estimate] = await Promise.all([
    api("/api/workouts/?limit=30"),
    api(`/api/plans/active?user_id=${userId}`),
    api(`/api/analytics/estimates?user_id=${userId}`),
  ]);

  const fitness = estimate.fitness;

  return [
    h("div", { class: "home-grid" },
      h("div", {},
        heroPanel(nextSession(plan), estimate),
        weekPanel(plan, workouts),
        h("section", {},
          h("div", { class: "row spread", style: "margin-bottom:8px" },
            h("h2", { style: "margin:0" }, "Laatste trainingen"),
            h("a", { href: "#trainingen" }, "Alles bekijken")
          ),
          workouts.length
            ? h("div", { class: "workout-list" }, workouts.slice(0, 4).map((workout) => workoutRow(workout)))
            : h("p", { class: "muted" }, "Nog geen trainingen. Voeg er een toe of haal ze op via Profiel.")
        )
      ),
      h("div", {},
        playerPanel(),
        fitness && h("div", { class: "tiles", style: "margin:0" },
          tile(formLabel(fitness.form), "vorm"),
          tile(decimal(fitness.fitness, 0), "fitheid"),
          estimate.running_index && tile(decimal(estimate.running_index.average, 0), "Running Index")
        ),
        questPanel()
      )
    ),
  ];
}

function weeklyPanel(weeks) {
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

  select("distance");

  return h("section", { class: "card" }, buttons, slot);
}

/* ---------- trainings ---------- */

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
  const sports = Object.entries(SPORTS).filter(([key]) => key !== "STRENGTH");

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

async function trainings() {
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

/* ---------- coach and plan ---------- */

const GOALS = {
  "5K": "5 km",
  "10K": "10 km",
  HALF: "Halve marathon",
  TRIATHLON: "Triatlon",
  STRENGTH: "Kracht",
  FITNESS: "Algemene conditie",
};

const WEEKDAY_NAMES = ["ma", "di", "wo", "do", "vr", "za", "zo"];

function weekdayPicker(selected) {
  return h("fieldset", { class: "day-picker" },
    h("legend", {}, "Op welke dagen train je? Het aantal dagen bepaalt het aantal trainingen per week."),
    WEEKDAY_NAMES.map((name, index) => {
      const input = h("input", { type: "checkbox", name: "day", value: index, "aria-label": name });
      input.checked = selected.includes(index);

      return h("label", {}, input, h("span", { "aria-hidden": "true" }, name));
    })
  );
}

function pickedDays(form) {
  return [...form.querySelectorAll("input[name=day]:checked")].map((input) => Number(input.value));
}

function sessionRow(session) {
  const state = session.completed ? "completed" : session.missed ? "missed" : "";

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
      "aria-label": session.completed ? "Gedaan" : session.missed ? "Gemist" : "Nog te doen",
    }, session.completed ? "✓" : session.missed ? "×" : ""),
    h("div", {},
      h("strong", {}, session.title),
      h("span", { class: "muted" },
        ` · ${dayLabel(session.date, { weekday: "short", day: "numeric", month: "short" })}`,
        ` · ${SPORTS[session.sport]}`,
        details.length ? ` · ${details.join(" · ")}` : "")
    ),
    h("p", {}, session.description),
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

function planForm(hasPlan) {
  return h("form", {
    onsubmit: submitter(async (form) => {
      const values = fields(form);
      const weekdays = pickedDays(form);

      if (weekdays.length < 2) throw new Error("Kies minstens twee dagen");

      if (hasPlan && !confirm("Je huidige plan vervangen? Wat je al deed, blijft meetellen voor je XP.")) {
        return;
      }

      await api("/api/plans/", {
        json: {
          user_id: userId,
          goal: values.goal,
          weekdays,
          weeks: values.race_date || !values.weeks ? null : Number(values.weeks),
          race_date: values.race_date || null,
        },
      });

      route();
    }),
  },
    h("div", { class: "fields" },
      h("label", {}, "Doel",
        h("select", { name: "goal" },
          Object.entries(GOALS).map(([key, label]) => h("option", { value: key }, label))
        )
      ),
      h("label", {}, "Wedstrijddatum (optioneel)", h("input", { name: "race_date", type: "date" })),
      h("label", {}, "Of aantal weken", h("input", {
        name: "weeks", type: "number", min: 2, max: 30, placeholder: "Automatisch", inputmode: "numeric",
      }))
    ),
    weekdayPicker([1, 3, 5, 6]),
    h("div", {}, h("button", { class: "primary", type: "submit" },
      hasPlan ? "Nieuw plan maken" : "Maak mijn plan"))
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
          json: { user_id: userId, weekdays },
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
    h("div", { class: "row", style: "margin-top:12px" },
      h("a", {
        class: "button",
        href: `/api/plans/active/calendar.ics?user_id=${userId}`,
        download: "trainmetrics-plan.ics",
      }, art("calendar"), "Zet in je agenda (.ics)")
    ),
    h("div", { style: "margin-top:12px" },
      [...weeks.entries()].map(([week, sessions]) =>
        h("details", { class: "week", open: week === currentWeek },
          h("summary", {},
            `Week ${week}`,
            ` · ${sessions.filter((session) => session.completed).length}/${sessions.length}`),
          sessions.map(sessionRow)
        )
      )
    )
  );
}

async function coachView() {
  const plan = await api(`/api/plans/active?user_id=${userId}`);

  const opening = plan
    ? plan.warning || `${GOALS[plan.goal]}, hè. Goed. Doe wat er staat, niet wat je zin hebt. En als iets pijn doet, zeg je het.`
    : "Vertel me wat je wilt bereiken en hoe vaak je kunt komen. Dan zet ik er een plan tegenover. Daar hoeft de laptop niet eens voor aan.";

  const dialog = coachDialog(opening);

  const ask = async (question) => {
    dialog.say("Effe nadenken...");

    try {
      const result = await api("/api/coach/ask", {
        json: { user_id: userId, question },
      });

      dialog.say(result.answer);
    } catch (error) {
      dialog.say(`${error.message}\n\nJe plan werkt gewoon, alleen mijn praatjes niet.`);
    }
  };

  const presets = plan
    ? ["Leg mijn plan van deze week uit", "Hoe ver sta ik met mijn doel?", "Ben ik goed bezig?"]
    : ["Hoe ga ik de laatste weken?", "Wat moet ik eerst aanpakken?"];

  return [
    h("h1", {}, "Plan"),
    dialog.element,
    plan && planPanel(plan),
    plan && schedulePanel(plan),
    h("section", { class: "card" },
      h("h2", {}, plan ? "Ander doel" : "Nieuw plan"),
      planForm(Boolean(plan))
    ),
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
}

/* ---------- performance ---------- */

function formLabel(form) {
  if (form > 5) return "fris";
  if (form < -10) return "moe";
  return "in balans";
}

function predictionPanel(estimate) {
  const index = estimate.running_index;
  const best = estimate.best_run;
  const distances = ["5 km", "10 km", "Halve marathon", "Marathon"];
  const hasIndex = Boolean(index?.predictions);

  if (!hasIndex && !best) {
    return h("section", { class: "card" },
      h("h2", {}, "Geschatte racetijden"),
      h("p", { class: "muted" }, "Loop minstens 3 km of synchroniseer met Polar, dan schat de coach je tijden."));
  }

  const columns = [{ label: "Afstand", value: (name) => name }];

  if (hasIndex) {
    columns.push({ label: `Polar (Running Index ${decimal(index.average)})`, value: (name) => clock(index.predictions[name]) });
  }

  if (best) {
    columns.push({ label: "Op basis van je snelste loop", value: (name) => clock(best.predictions[name]) });
  }

  return h("section", { class: "card" },
    h("h2", {}, "Geschatte racetijden"),
    table(columns, distances),
    h("p", { class: "muted", style: "margin:12px 0 0" },
      hasIndex ? `De Polar-kolom gebruikt het gemiddelde van je laatste ${index.sample_size} Running Index-waarden en de tabel van Polar. ` : "",
      best ? `De andere kolom rekent met de formule van Riegel vanuit je ${kilometers(best.distance)} van ${dayLabel(best.date)}. Was dat geen volle inspanning, dan kun je sneller. ` : "",
      "Dit zijn schattingen bij een maximale inspanning, geen beloftes.")
  );
}

const PERIODS = [
  ["", "Alles"],
  ["365", "Laatste jaar"],
  ["90", "Laatste 90 dagen"],
  ["30", "Laatste 30 dagen"],
];

function sportHeadline(row) {
  if (row.sport === "STRENGTH") {
    return row.strength.volume_kg
      ? `${decimal(row.strength.volume_kg / 1000)} ton`
      : duration(row.duration_seconds);
  }

  return row.distance_meters ? kilometers(row.distance_meters) : duration(row.duration_seconds);
}

function sportTrend(row) {
  const change = row.last_28_days - row.previous_28_days;

  if (!row.last_28_days && !row.previous_28_days) return "Geen trainingen in de laatste 8 weken.";

  const word = change > 0 ? `${change} meer dan` : change < 0 ? `${-change} minder dan` : "evenveel als";

  return `${row.last_28_days} ${row.last_28_days === 1 ? "training" : "trainingen"} in de laatste 4 weken, ${word} de 4 weken ervoor.`;
}

function sportDetail(row) {
  const pseudo = { activity_type: row.sport, average_speed: row.average_speed };
  const isStrength = row.sport === "STRENGTH";
  const hasDistance = row.distance_meters > 0;

  const tiles = [
    tile(decimal(row.sessions, 0), row.sessions === 1 ? "training" : "trainingen"),
    tile(duration(row.duration_seconds), "totale tijd"),
    hasDistance && tile(kilometers(row.distance_meters), "afstand"),
    row.average_speed && tile(pace(pseudo), row.sport === "CYCLING" ? "gemiddeld" : "gemiddeld tempo"),
    row.average_heart_rate && tile(`${row.average_heart_rate}`, "gem. hartslag"),
    row.elevation_gain > 0 && tile(`${decimal(row.elevation_gain, 0)} m`, "hoogtemeters"),
    row.calories > 0 && tile(decimal(row.calories, 0), "kcal"),
    row.best_running_index && tile(String(row.best_running_index), "beste Running Index"),
    isStrength && row.strength.sets > 0 && tile(decimal(row.strength.sets, 0), "sets"),
    isStrength && row.strength.volume_kg > 0 && tile(`${decimal(row.strength.volume_kg, 0)} kg`, "volume"),
  ];

  const records = [
    row.longest && ["Langste", `${kilometers(row.longest.distance)} op ${dayLabel(row.longest.date)}`],
    row.fastest && ["Snelste", `${pace({ activity_type: row.sport, average_speed: row.fastest.speed })} over ${kilometers(row.fastest.distance)}, ${dayLabel(row.fastest.date)}`],
    isStrength && row.strength.best_lift && ["Sterkste", `${row.strength.best_lift.exercise}: geschat 1RM ${decimal(row.strength.best_lift.estimated_1rm_kg)} kg, ${dayLabel(row.strength.best_lift.date)}`],
  ].filter(Boolean);

  const hasWeeklyDistance = row.weekly.some((week) => week.distance_meters > 0);

  const chart = hasWeeklyDistance
    ? {
      title: "Afstand per week, laatste 26 weken",
      y: (week) => week.distance_meters / 1000,
      format: (value) => `${decimal(value)} km`,
      label: "Afstand",
    }
    : {
      title: "Trainingstijd per week, laatste 26 weken",
      y: (week) => week.duration_seconds / 60,
      format: (value) => `${decimal(value, 0)} min`,
      label: "Tijd",
    };

  return h("div", {},
    h("div", { class: "row", style: "margin-bottom:10px;gap:10px" },
      h("div", { class: "scene-chip", style: "width:110px" }, art(row.sport)),
      h("p", { class: "trend", style: "margin:0;flex:1;min-width:180px" }, sportTrend(row))
    ),
    h("div", { class: "tiles" }, tiles),
    barChart(chart.title, row.weekly, {
      x: (week) => shortDay(week.week_start),
      y: chart.y,
      format: chart.format,
      columns: [
        { label: "Week van", value: (week) => dayLabel(week.week_start) },
        { label: "Trainingen", value: (week) => String(week.sessions) },
        { label: chart.label, value: (week) => chart.format(chart.y(week)) },
      ],
    }),
    records.length > 0 && h("div", { style: "margin-top:12px" },
      h("h3", {}, "Records"),
      table([
        { label: "", value: (record) => record[0] },
        { label: "", value: (record) => record[1] },
      ], records)
    )
  );
}

function sportPanel() {
  const body = h("div", {});
  let selected = null;

  const load = async (days) => {
    const result = await api(`/api/analytics/sports?user_id=${userId}${days ? `&days=${days}` : ""}`);
    const rows = result.sports.filter((row) => row.sessions > 0);

    if (!rows.length) {
      body.replaceChildren(h("p", { class: "muted" }, "Geen trainingen in deze periode."));
      return;
    }

    if (!rows.some((row) => row.sport === selected)) selected = rows[0].sport;

    const detail = h("div", {});
    const cards = h("div", { class: "sport-cards" });

    const select = (sport) => {
      selected = sport;

      cards.querySelectorAll("button").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.sport === sport));
      });

      detail.replaceChildren(sportDetail(rows.find((row) => row.sport === sport)));
    };

    rows.forEach((row) => {
      const icon = art(`icon_${row.sport}`);

      cards.append(h("button", {
        class: "sport-card",
        type: "button",
        "data-sport": row.sport,
        onclick: () => select(row.sport),
      },
        h("span", { class: "name" }, icon, SPORTS[row.sport]),
        h("b", {}, sportHeadline(row)),
        h("small", {}, `${row.sessions} × · ${Math.round(row.share_of_time * 100)}% van je tijd`),
        h("span", { class: "share" }, h("i", { style: `width:${row.share_of_time * 100}%` }))
      ));
    });

    body.replaceChildren(cards, detail);
    select(selected);
  };

  const period = h("select", {
    "aria-label": "Periode",
    style: "width:auto",
    onchange: (event) => load(event.target.value).catch((error) => {
      body.replaceChildren(message(error.message, true));
    }),
  }, PERIODS.map(([value, label]) => h("option", { value }, label)));

  load("").catch((error) => body.replaceChildren(message(error.message, true)));

  return h("section", { class: "card" },
    h("div", { class: "row spread", style: "margin-bottom:12px" },
      h("h2", { style: "margin:0" }, "Per sport"),
      period
    ),
    body
  );
}

async function statisticsView() {
  const [weeks, estimate, exercises, records, rows, weights] = await Promise.all([
    api(`/api/analytics/weekly?user_id=${userId}`),
    api(`/api/analytics/estimates?user_id=${userId}`),
    api("/api/exercises/"),
    api(`/api/analytics/records?user_id=${userId}`),
    api("/api/body-measurements/"),
    api(`/api/analytics/body-weight?user_id=${userId}`),
  ]);

  const progressSlot = h("div", {});

  const showExercise = async (exerciseId) => {
    const progress = await api(`/api/analytics/exercises/${exerciseId}/progress?user_id=${userId}`);
    const format = (value) => `${decimal(value)} kg`;

    progressSlot.replaceChildren(progress.length
      ? lineChart("Geschat 1RM per trainingsdag", progress, {
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

  const initial = records[0]?.exercise_id ?? exercises[0]?.id;

  if (initial !== undefined) await showExercise(initial);

  const fitness = estimate.fitness;
  const value = (amount, unit) => (amount === null ? "–" : `${decimal(amount)} ${unit}`);

  const removeMeasurement = async (row) => {
    if (!confirm(`Meting van ${dayLabel(row.date)} verwijderen?`)) return;

    await api(`/api/body-measurements/${row.id}`, { method: "DELETE" });
    route();
  };

  return [
    h("h1", {}, "Statistieken"),
    fitness && h("div", { class: "tiles" },
      tile(decimal(fitness.fitness, 0), "fitheid"),
      tile(decimal(fitness.fatigue, 0), "vermoeidheid"),
      tile(formLabel(fitness.form), `vorm (${decimal(fitness.form, 0)})`),
      estimate.running_index && tile(decimal(estimate.running_index.average), "Running Index")
    ),
    weeklyPanel(weeks),
    sportPanel(),
    fitness && h("section", { class: "card" },
      lineChart("Fitheid, laatste 90 dagen", estimate.fitness_series, {
        x: (row) => row.date,
        y: (row) => row.fitness,
        format: (amount) => decimal(amount, 0),
        columns: [
          { label: "Datum", value: (row) => dayLabel(row.date) },
          { label: "Fitheid", value: (row) => decimal(row.fitness) },
          { label: "Vermoeidheid", value: (row) => decimal(row.fatigue) },
          { label: "Vorm", value: (row) => decimal(row.form) },
        ],
      }),
      h("p", { class: "muted", style: "margin:12px 0 0" },
        `Geschat uit je trainingen: fitheid is je inspanning van de laatste 6 weken, vermoeidheid die van de laatste week, en vorm het verschil. De inspanning komt uit duur en hartslag, met een maximale hartslag van ${estimate.max_heart_rate}.`)
    ),
    predictionPanel(estimate),
    estimate.running_index?.trend.length > 1 && h("section", { class: "card" },
      lineChart("Running Index", estimate.running_index.trend, {
        x: (row) => row.date,
        y: (row) => row.running_index,
        format: (amount) => decimal(amount, 0),
        columns: [
          { label: "Datum", value: (row) => dayLabel(row.date) },
          { label: "Running Index", value: (row) => String(row.running_index) },
        ],
      })
    ),
    exercises.length > 0 && h("section", { class: "card" },
      h("h2", {}, "Kracht"),
      h("label", { style: "margin-bottom:12px" }, "Oefening",
        h("select", {
          onchange: (event) => showExercise(event.target.value).catch((error) => {
            progressSlot.replaceChildren(message(error.message, true));
          }),
        }, exercises.map((exercise) => {
          const option = h("option", { value: exercise.id }, exercise.name);
          option.selected = exercise.id === initial;
          return option;
        }))
      ),
      progressSlot,
      h("h3", { style: "margin-top:16px" }, "Persoonlijke records"),
      records.length
        ? table([
          { label: "Oefening", value: (row) => row.exercise },
          { label: "Zwaarste set", value: (row) => `${decimal(row.top_weight_kg)} kg` },
          { label: "Geschat 1RM", value: (row) => `${decimal(row.estimated_1rm_kg)} kg` },
          { label: "Op", value: (row) => dayLabel(row.estimated_1rm_date) },
        ], records)
        : h("p", { class: "muted" }, "Nog geen records."),
      h("p", { class: "muted", style: "margin:12px 0 0" },
        "Het geschatte 1RM gebruikt de Epley-formule: gewicht × (1 + herhalingen / 30).")
    ),
    h("section", { class: "card" },
      h("h2", {}, "Metingen"),
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
      ),
      weights.length > 0 && h("div", { style: "margin-top:16px" }, weightChart(weights)),
      rows.length > 0 && h("div", { style: "margin-top:16px" }, table([
        { label: "Datum", value: (row) => dayLabel(row.date) },
        { label: "Gewicht", value: (row) => value(row.weight, "kg") },
        { label: "Vet", value: (row) => value(row.body_fat, "%") },
        { label: "Taille", value: (row) => value(row.waist, "cm") },
        { label: "Borst", value: (row) => value(row.chest, "cm") },
        {
          label: "",
          value: (row) => h("button", {
            class: "danger small", type: "button", onclick: () => removeMeasurement(row),
          }, "Verwijderen"),
        },
      ], rows))
    ),
  ];
}

/* ---------- trophies ---------- */

function trophies() {
  const earned = game.badges.filter((badge) => badge.earned_on).length;

  return [
    art("trophy"),
    h("h1", {}, "Trofeeën"),
    playerPanel(),
    h("section", { class: "card" },
      h("h2", {}, `Badges (${earned} van ${game.badges.length})`),
      h("div", { class: "badges" }, game.badges.map((badge) =>
        h("div", { class: `badge ${badge.earned_on ? "earned" : "locked"}` },
          medal(Boolean(badge.earned_on)),
          h("h3", {}, badge.name),
          h("p", { class: "muted", style: "margin:0" }, badge.description),
          badge.earned_on
            ? h("p", { class: "muted", style: "margin:4px 0 0" }, dayLabel(badge.earned_on))
            : badge.target > 1 && h("p", { class: "muted", style: "margin:4px 0 0" }, `${badge.progress} / ${badge.target}`)
        )
      ))
    ),
    game.recent.length > 0 && h("section", { class: "card" },
      h("h2", {}, "Laatst verdiend"),
      table([
        { label: "XP", value: (row) => `+${row.xp}` },
        { label: "Waarvoor", value: (row) => row.label },
        { label: "Datum", value: (row) => dayLabel(row.date) },
      ], game.recent)
    ),
    h("p", { class: "muted" },
      "Je scoort XP met elke training (meer als die zwaarder was), records, quests, plantrainingen en metingen."),
  ];
}

/* ---------- sync ---------- */

const POLAR_RESULTS = {
  gekoppeld: ["Je Polar-account is gekoppeld. Klik op Nu ophalen voor je trainingen.", false],
  geweigerd: ["Het koppelen is niet gelukt of werd geweigerd. Probeer het opnieuw.", true],
  mislukt: ["Polar weigerde de koppeling. Controleer je client-ID en secret, en probeer het opnieuw.", true],
};

async function syncView() {
  const status = await api(`/api/polar/status?user_id=${userId}`);
  const result = POLAR_RESULTS[new URLSearchParams(location.hash.split("?")[1]).get("polar")];
  const output = h("div", { "aria-live": "polite" }, result && message(...result));
  const results = h("div", { "aria-live": "polite" });

  const fetchNow = async (event) => {
    const button = event.currentTarget;
    button.disabled = true;

    try {
      const counts = await api(`/api/polar/sync?user_id=${userId}`, { method: "POST" });

      await route();

      const total = counts.imported + counts.updated + counts.skipped;

      document.getElementById("polar-output")?.replaceChildren(message(
        total
          ? `${counts.imported} nieuw, ${counts.updated} aangevuld, ${counts.skipped} waren er al.`
          : "De koppeling werkt, maar Polar heeft nog geen trainingen voor deze app. Polar geeft alleen trainingen die na het koppelen naar Polar Flow zijn geüpload. Je volgende training komt dus vanzelf door; oudere upload je hieronder als bestand."
      ));
    } catch (error) {
      output.replaceChildren(message(error.message, true));
      button.disabled = false;
    }
  };

  const unlink = async () => {
    if (!confirm("Polar ontkoppelen? Je trainingen blijven staan.")) return;

    await api(`/api/polar/link?user_id=${userId}`, { method: "DELETE" });
    location.hash = "#profiel";
    route();
  };

  output.id = "polar-output";

  let polar;

  if (!status.configured) {
    polar = [
      h("p", {}, "De koppeling is nog niet ingesteld. Maak een gratis API-client aan op ",
        h("a", { href: "https://admin.polaraccesslink.com", target: "_blank", rel: "noreferrer" }, "admin.polaraccesslink.com"),
        " en zet de gegevens in backend/.env. De stappen staan in docs/deployment.md."),
    ];
  } else if (!status.linked) {
    polar = [
      h("p", {}, "Koppel je Polar-account. Daarna komen nieuwe trainingen vanzelf hierheen, inclusief je Running Index."),
      h("a", { class: "button primary", href: `/api/polar/connect?user_id=${userId}` }, "Koppel met Polar"),
    ];
  } else {
    polar = [
      h("p", {}, status.last_sync_at
        ? `Laatst opgehaald: ${dayLabel(status.last_sync_at)} om ${status.last_sync_at.slice(11, 16)}.`
        : "Gekoppeld, maar nog niets opgehaald."),
      h("div", { class: "row" },
        h("button", { class: "primary", type: "button", onclick: fetchNow }, "Nu ophalen"),
        h("button", { class: "small", type: "button", onclick: unlink }, "Ontkoppelen")
      ),
    ];
  }

  return [
    h("section", { class: "card" },
      h("h2", {}, "Polar"),
      output,
      polar,
      h("p", { class: "muted", style: "margin:12px 0 0" },
        "Polar geeft alleen trainingen uit de laatste 30 dagen die na het koppelen zijn geüpload. Oudere trainingen upload je hieronder als bestand.")
    ),
    h("section", { class: "card" },
      h("h2", {}, "Bestanden"),
      h("p", {}, "Upload FIT-, GPX- of TCX-bestanden. Wat je al importeerde, wordt overgeslagen."),
      h("p", { class: "muted" }, "Polar Flow: open een training en exporteer als TCX. Garmin Connect: exporteer het origineel (FIT)."),
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
          await refreshGame();
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

/* ---------- management ---------- */

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
      failure.scrollIntoView({ block: "center" });
    }
  };

  return [
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

async function profileView() {
  const [sync, manage] = await Promise.all([syncView(), management()]);

  return [
    h("h1", {}, "Profiel"),
    sync,
    manage,
    h("p", { class: "muted" },
      "Afbeeldingen: ",
      h("a", { href: "https://github.com/microsoft/fluentui-emoji", target: "_blank", rel: "noreferrer" }, "Fluent Emoji"),
      " van Microsoft (MIT) en ",
      h("a", { href: "https://googlefonts.github.io/noto-emoji-animation/", target: "_blank", rel: "noreferrer" }, "Noto Animated Emoji"),
      " van Google (",
      h("a", { href: "https://creativecommons.org/licenses/by/4.0/", target: "_blank", rel: "noreferrer" }, "CC BY 4.0"),
      ")."),
  ];
}

function setupView() {
  return [
    coachDialog("Nieuw gezicht. Hoe heet je? En ga niet zitten, we zijn er nog niet.").element,
    h("section", { class: "card" },
      h("form", {
        onsubmit: submitter(async (form) => {
          const created = await api("/api/users/", { json: fields(form) });
          userId = created.id;
          location.hash = "#vandaag";
          route();
        }),
      },
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
  vandaag: overview,
  trainingen: trainings,
  plan: coachView,
  statistieken: statisticsView,
  trofeeen: trophies,
  profiel: profileView,
};

let routeCounter = 0;

async function route() {
  const current = ++routeCounter;
  const name = location.hash.slice(1).split("?")[0];
  const view = VIEWS[name] ? name : "vandaag";

  document.querySelectorAll("[data-view]").forEach((link) => {
    if (link.dataset.view === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
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

    await refreshGame();

    const content = await VIEWS[view]();

    // A slower earlier view must not overwrite the page the user went to.
    if (current === routeCounter) {
      app.replaceChildren(...[content].flat(3).filter(Boolean));
    }
  } catch (error) {
    if (current === routeCounter) app.replaceChildren(message(error.message, true));
  }
}

window.addEventListener("hashchange", route);
route();
