import { segmentsPanel } from "./segments.js";
import { zoneBars } from "./workout-detail.js";
import { api } from "../api.js";
import { art, drawRoutes } from "../art.js";
import { barChart, lineChart, seriesChart } from "../charts.js";
import { fields, h, message, number, subTabs, submitter, table, tile } from "../dom.js";
import { SPORTS, clock, dayLabel, decimal, duration, formLabel, kilometers, lengthLabel, localNow, pace, shortDay } from "../format.js";
import { route } from "../navigation.js";
import { weightChart } from "../workouts.js";

function sleepPanel(sleep) {
  const averages = sleep.averages;
  const recovery = sleep.recovery;
  const phase = (seconds) => (seconds ? duration(seconds) : "–");

  const scoreRows = sleep.nights.filter((night) => night.sleep_score !== null);
  const hrvRows = sleep.nights.filter((night) => night.hrv_ms);
  const durationRows = sleep.nights.filter((night) => night.asleep_seconds);

  const dayOf = (night) => dayLabel(night.night);

  return h("section", { class: "card" },
    h("div", { class: "row spread", style: "margin-bottom:12px" },
      h("h2", { style: "margin:0" }, "Slaap en herstel"),
      h("span", { class: "muted" }, `gemiddelde van ${averages.nights} nachten`)
    ),
    h("div", { class: "tiles" },
      averages.asleep_seconds && tile(duration(averages.asleep_seconds), "slaap per nacht"),
      averages.sleep_score && tile(decimal(averages.sleep_score, 0), "slaapscore"),
      averages.deep_seconds && tile(phase(averages.deep_seconds), "diepe slaap"),
      averages.rem_seconds && tile(phase(averages.rem_seconds), "REM-slaap"),
      averages.hrv_ms && tile(`${decimal(averages.hrv_ms, 0)} ms`, "hartslagvariabiliteit"),
      averages.heart_rate && tile(`${decimal(averages.heart_rate, 0)} bpm`, "hartslag in je slaap"),
      averages.breathing_rate && tile(decimal(averages.breathing_rate), "ademhalingen per minuut")
    ),
    durationRows.length > 1 && barChart("Slaap per nacht", durationRows, {
      x: (night) => shortDay(night.night),
      y: (night) => night.asleep_seconds / 3600,
      format: (value) => `${decimal(value)} u`,
      tip: dayOf,
      columns: [
        { label: "Nacht", value: dayOf },
        { label: "Slaap", value: (night) => duration(night.asleep_seconds) },
        { label: "Diep", value: (night) => phase(night.deep_seconds) },
        { label: "REM", value: (night) => phase(night.rem_seconds) },
        { label: "Score", value: (night) => (night.sleep_score ?? "–").toString() },
      ],
    }),
    scoreRows.length > 1 && h("div", { style: "margin-top:16px" }, lineChart("Slaapscore", scoreRows, {
      x: (night) => night.night,
      y: (night) => night.sleep_score,
      format: (value) => decimal(value, 0),
      columns: [
        { label: "Nacht", value: dayOf },
        { label: "Slaapscore", value: (night) => String(night.sleep_score) },
      ],
    })),
    hrvRows.length > 1 && h("div", { style: "margin-top:16px" }, lineChart("Hartslagvariabiliteit in je slaap", hrvRows, {
      x: (night) => night.night,
      y: (night) => night.hrv_ms,
      format: (value) => `${decimal(value, 0)} ms`,
      columns: [
        { label: "Nacht", value: dayOf },
        { label: "Variabiliteit", value: (night) => `${night.hrv_ms} ms` },
      ],
    })),
    recovery && h("p", { class: "muted", style: "margin:12px 0 0" },
      recovery.source === "POLAR"
        ? "Je herstel komt van Polars Nightly Recharge. Het is geen medisch advies."
        : `Polar gaf voor deze nacht geen Nightly Recharge. Dit is een schatting van deze app: je hartslagvariabiliteit (${recovery.hrv_ms} ms) tegenover je eigen normaal van ${recovery.baseline_nights} nachten (${recovery.baseline_ms} ms). Het is geen medisch advies.`)
  );
}

function routesPanel() {
  const body = h("div", {});
  const sports = h("select", { "aria-label": "Sport", style: "width:auto" },
    h("option", { value: "" }, "Alle sporten"),
    ["RUNNING", "CYCLING", "SWIMMING", "OTHER"].map((sport) => h("option", { value: sport }, SPORTS[sport]))
  );

  const show = async () => {
    const element = h("div", { class: "route-map large" });
    const note = h("p", { class: "muted", style: "margin:0" });
    body.replaceChildren(element, note);

    try {
      const query = sports.value ? `?sport=${sports.value}` : "";
      const routes = await api(`/api/routes${query}`);

      if (!routes.length) {
        body.replaceChildren(h("p", { class: "muted" }, "Geen routes voor deze sport."));
        return;
      }

      note.textContent = `${routes.length} ${routes.length === 1 ? "route" : "routes"}. De kaart opent waar je het meest traint; zoom uit voor de rest. Klik op een lijn om te zien welke training het was.`;

      await drawRoutes(element, routes.map((route) => ({
        points: route.points,
        label: `${SPORTS[route.sport]}, ${dayLabel(route.date)}`,
      })));
    } catch (error) {
      body.replaceChildren(message(error.message, true));
    }
  };

  body.append(
    h("p", { class: "muted" }, "De kaart komt van OpenStreetMap en laadt pas als je erom vraagt, want die dienst ziet dan welk gebied je bekijkt. Je trainingen zelf blijven bij jou.")
  );

  return h("section", { class: "card" },
    h("div", { class: "row spread", style: "margin-bottom:12px" },
      h("h2", { style: "margin:0" }, "Routes"),
      h("div", { class: "row" },
        sports,
        h("button", { class: "primary small", type: "button", onclick: show }, art("map"), "Toon op kaart")
      )
    ),
    body
  );
}

function performancePanel(chart, maxHeartRate) {
  if (!chart.history.length) {
    return h("section", { class: "card" }, h("h2", {}, "Prestatiegrafiek"), h("p", { class: "muted" }, "Nog geen trainingen."));
  }

  const past = chart.history.map((row) => ({ ...row, projected: false }));
  const future = chart.projection.map((row) => ({ ...row, projected: true }));
  const rows = [...past, ...future];
  const time = (date) => new Date(`${date}T12:00:00`).getTime();
  const comingRaces = chart.races.filter((race) => race.form !== null);
  const today = past.at(-1);

  const format = (value) => decimal(value, 0);

  return h("section", { class: "card" },
    seriesChart("Fitheid, vermoeidheid en vorm", rows, {
      x: (row) => time(row.date),
      xFormat: (value) => shortDay(new Date(value).toLocaleDateString("sv")),
      format,
      projected: (row) => row.projected,
      marks: [
        { x: time(today.date), label: "vandaag" },
        ...comingRaces.map((race) => ({ x: time(race.date), label: `${race.priority}: ${race.name}` })),
      ],
      series: [
        { label: "Fitheid", color: "#6E0D25", value: (row) => row.fitness },
        { label: "Vermoeid", color: "#E0784F", value: (row) => row.fatigue },
        { label: "Vorm", color: "#2F7FB5", value: (row) => row.form },
      ],
      columns: [
        { label: "Datum", value: (row) => dayLabel(row.date) },
        { label: "Fitheid", value: (row) => format(row.fitness) },
        { label: "Vermoeidheid", value: (row) => format(row.fatigue) },
        { label: "Vorm", value: (row) => format(row.form) },
      ],
    }),
    comingRaces.length > 0 && h("ul", { class: "highlights", style: "margin-top:10px" },
      comingRaces.map((race) => h("li", {}, h("b", {}, `${race.name}: `),
        `verwachte vorm ${format(race.form)} op ${dayLabel(race.date)}`))),
    h("p", { class: "muted", style: "margin:10px 0 0" },
      `Geschat uit duur en hartslag, met een maximale hartslag van ${maxHeartRate}. Fitheid is je inspanning van de laatste 6 weken, vermoeidheid die van de laatste week en vorm het verschil. De stippellijn is een schatting als je je plan volgt, met een gemiddelde zwaarte per training. Je wilt op wedstrijddag bij voorkeur boven nul zitten.`)
  );
}

function zonesPanel(summary) {
  if (!summary.zones.some((zone) => zone.seconds)) {
    return h("section", { class: "card" }, h("h2", {}, "Hartslagzones"), h("p", { class: "muted" }, "Geen hartslagdata in deze periode."));
  }

  const weeks = summary.per_week.filter((week) => week.easy_share !== null);

  return h("section", { class: "card" },
    h("div", { class: "row spread", style: "margin-bottom:10px" },
      h("h2", { style: "margin:0" }, "Hartslagzones"),
      h("span", { class: "muted" }, `laatste ${summary.weeks} weken`)
    ),
    zoneBars(summary.zones),
    h("p", { style: "margin:12px 0" },
      h("b", {}, `${Math.round(summary.easy_share * 100)}% `),
      "van je trainingstijd zat in zone 1 en 2. Duursporters mikken vaak op ongeveer 80%, dus dit zegt iets over of je rustige trainingen echt rustig zijn."),
    weeks.length > 1 && barChart("Rustig aandeel per week", summary.per_week, {
      x: (week) => shortDay(week.week_start),
      y: (week) => (week.easy_share ?? 0) * 100,
      format: (value) => `${decimal(value, 0)}%`,
      columns: [
        { label: "Week van", value: (week) => dayLabel(week.week_start) },
        { label: "Zone 1 en 2", value: (week) => (week.easy_share === null ? "–" : `${Math.round(week.easy_share * 100)}%`) },
        { label: "Totaal", value: (week) => duration(week.seconds) },
      ],
    })
  );
}

function bestEffortsPanel(efforts) {
  const sports = ["RUNNING", "CYCLING", "SWIMMING"].filter((sport) => efforts.some((row) => row.sport === sport));

  return h("section", { class: "card" },
    h("h2", {}, "Beste prestaties"),
    !sports.length && h("p", { class: "muted" }, "Nog geen metingen."),
    sports.map((sport) => h("div", { style: "margin-bottom:12px" },
      h("h3", {}, SPORTS[sport]),
      table([
        { label: "Afstand", value: (row) => lengthLabel(row.meters) },
        { label: "Beste", value: (row) => clock(row.best[0].seconds) },
        { label: sport === "CYCLING" ? "Snelheid" : "Tempo", value: (row) => pace({ activity_type: sport, average_speed: row.meters / row.best[0].seconds }) },
        { label: "Op", value: (row) => dayLabel(row.best[0].date) },
        { label: "Daarna", value: (row) => row.best.slice(1).map((time) => clock(time.seconds)).join(", ") || "–" },
      ], efforts.filter((row) => row.sport === sport))
    )),
    sports.length > 0 && h("p", { class: "muted", style: "margin:0" },
      "De snelste stukken uit al je trainingen, dus ook binnen een langere loop. Duidelijke GPS-sprongen tellen niet mee.")
  );
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
      best ? `De andere kolom rekent met de formule van Riegel vanuit ${best.is_stretch ? "je snelste stuk van" : "je"} ${kilometers(best.distance)} op ${dayLabel(best.date)}. Was dat geen volle inspanning, dan kun je sneller. ` : "",
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
      h("div", { class: "scene-chip" }, art(row.sport)),
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
    const result = await api(`/api/analytics/sports${days ? `?days=${days}` : ""}`);
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

export async function statisticsView() {
  const [performance, zones, efforts, segments, sleep, weeks, estimate, exercises, records, rows, weights] = await Promise.all([
    api("/api/analytics/performance"),
    api("/api/analytics/zones"),
    api("/api/analytics/best-efforts"),
    segmentsPanel(),
    api(`/api/analytics/sleep`),
    api(`/api/analytics/weekly`),
    api(`/api/analytics/estimates`),
    api("/api/exercises/"),
    api(`/api/analytics/records`),
    api("/api/body-measurements/"),
    api(`/api/analytics/body-weight`),
  ]);

  const progressSlot = h("div", {});

  const showExercise = async (exerciseId) => {
    const progress = await api(`/api/analytics/exercises/${exerciseId}/progress`);
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
    subTabs("statistics", [
      {
        label: "Belasting",
        content: [
    fitness && h("div", { class: "tiles" },
      tile(decimal(fitness.fitness, 0), "fitheid"),
      tile(decimal(fitness.fatigue, 0), "vermoeidheid"),
      tile(formLabel(fitness.form), `vorm (${decimal(fitness.form, 0)})`),
      estimate.running_index && tile(decimal(estimate.running_index.average), "Running Index")
    ),
          performancePanel(performance, estimate.max_heart_rate),
          weeklyPanel(weeks),
          zonesPanel(zones),
        ],
      },
      {
        label: "Sporten",
        content: [
          sportPanel(),
          bestEffortsPanel(efforts),
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
        ],
      },
      { label: "Routes", content: [routesPanel(), segments] },
      {
        label: "Slaap",
        content: sleep.last_night
          ? sleepPanel(sleep)
          : h("p", { class: "muted" }, "Nog geen slaapdata. Die komt mee met de Polar-sync."),
      },
      {
        label: "Kracht en lichaam",
        content: [
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
        ],
      },
    ]),
  ];
}
