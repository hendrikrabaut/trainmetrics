import { api } from "./api.js";
import { h } from "./dom.js";
import { SPORTS, duration, isoDay, kilometers } from "./format.js";
import { playerPanel, refreshGame } from "./gamification.js";
import { ring } from "./ring.js";
import { nextSession, recoveryLabel, weekDays, whenLabel } from "./views/today.js";
import { workoutRow } from "./workouts.js";

const REFRESH_MINUTES = 5;
// A full reload now and then picks up a new version of the app.
const RELOAD_HOURS = 6;

const time = (date) => date.toLocaleTimeString("nl-BE", { hour: "2-digit", minute: "2-digit" });

function showClock() {
  const now = new Date();
  document.getElementById("wall-time").textContent = time(now);
  document.getElementById("wall-date").textContent =
    now.toLocaleDateString("nl-BE", { weekday: "long", day: "numeric", month: "long" });
}

function nextCard(next) {
  if (!next) {
    return h("section", { class: "wall-next" },
      h("span", { class: "eyebrow" }, "Volgende training"),
      h("h2", {}, "Nog niets gepland"),
      h("p", {}, "Maak een plan in de app."));
  }

  const facts = [
    SPORTS[next.sport],
    next.distance ? kilometers(next.distance) : null,
    next.duration ? duration(next.duration) : null,
  ].filter(Boolean);

  return h("section", { class: "wall-next" },
    h("span", { class: "eyebrow" }, `Volgende training · ${whenLabel(next.date)}`),
    h("h2", {}, next.title),
    h("p", { class: "facts" }, facts.join(" · ")),
    next.description && h("p", { class: "description" }, next.description));
}

function weekCard(plan, workouts) {
  const days = weekDays();
  const inWeek = new Set(days.map(isoDay));
  const today = isoDay(new Date());
  const planned = (plan?.sessions ?? []).filter((session) => inWeek.has(session.date));
  const trained = workouts.filter((workout) => inWeek.has(workout.date.slice(0, 10)));
  const finished = planned.filter((session) => session.completed).length;

  return h("section", { class: "card wall-week" },
    h("div", { class: "wall-pair" },
      planned.length
        ? ring(finished, planned.length, {
          size: "medium",
          label: `${finished} van ${planned.length} geplande trainingen gedaan`,
          center: h("b", {}, `${finished}/${planned.length}`),
        })
        : h("b", { class: "wall-count" }, String(trained.length)),
      h("h2", { style: "margin:0" }, "Deze week")
    ),
    h("div", { class: "wall-days" }, days.map((day) => {
      const key = isoDay(day);
      const done = trained.some((workout) => workout.date.startsWith(key));
      const todo = planned.some((session) => session.date === key && !session.completed);

      return h("div", { class: `wall-day${key === today ? " today" : ""}` },
        day.toLocaleDateString("nl-BE", { weekday: "narrow" }),
        h("i", { class: done ? "done" : todo ? "planned" : "" }));
    }))
  );
}

function sleepCard(sleep) {
  const night = sleep.is_recent ? sleep.last_night : null;

  if (!night) {
    return h("section", { class: "card wall-sleep" },
      h("h2", { style: "margin:0" }, "Afgelopen nacht"),
      h("span", { class: "muted" }, "Nog geen gegevens"));
  }

  const score = night.sleep_score;

  return h("section", { class: "card wall-sleep" },
    h("div", { class: "wall-pair" },
      score !== null && ring(score, 100, {
        size: "medium",
        label: `Slaapscore ${score} van 100`,
        center: [h("b", {}, String(score)), h("small", {}, "score")],
      }),
      h("div", {},
        h("h2", { style: "margin:0" }, "Slaap"),
        night.asleep_seconds && h("span", { class: "muted" }, duration(night.asleep_seconds)))
    ),
    sleep.recovery && h("span", { class: `recovery-pill ${sleep.recovery.status.toLowerCase()}` },
      recoveryLabel(sleep.recovery))
  );
}

async function refresh() {
  const status = document.getElementById("wall-status");

  try {
    const [plan, workouts, sleep] = await Promise.all([
      api("/api/plans/active"),
      api("/api/workouts/?limit=30"),
      api("/api/analytics/sleep"),
      refreshGame(),
    ]);

    document.getElementById("wall").replaceChildren(
      nextCard(nextSession(plan)),
      h("div", { class: "wall-grid" }, weekCard(plan, workouts), sleepCard(sleep)),
      playerPanel(),
      workouts.length > 0 && h("section", { class: "wall-last" },
        h("h2", {}, "Laatste training"),
        h("div", { class: "workout-list" }, workoutRow(workouts[0])))
    );

    status.textContent = `Bijgewerkt om ${time(new Date())}`;
  } catch (error) {
    // Keep the last good picture on screen and say how old it is.
    status.textContent = `${error.message}. ${status.textContent}`.slice(0, 120);
  }
}

showClock();
refresh();
setInterval(showClock, 20 * 1000);
setInterval(refresh, REFRESH_MINUTES * 60 * 1000);
setTimeout(() => location.reload(), RELOAD_HOURS * 60 * 60 * 1000);
