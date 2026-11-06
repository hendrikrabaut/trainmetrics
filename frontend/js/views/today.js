import { api } from "../api.js";
import { art, coachDialog } from "../art.js";
import { h, tile } from "../dom.js";
import { SPORTS, dayLabel, decimal, duration, formLabel, isoDay, kilometers, localNow } from "../format.js";
import { game, playerPanel, questPanel } from "../gamification.js";
import { workoutRow, workoutSport } from "../workouts.js";

function coachLine(next, estimate, sleep) {
  const open = game.quests.find((quest) => !quest.completed);
  const form = estimate.fitness?.form;

  if (game.xp === 0) {
    return "Dus jij wilt trainen. Dat zeggen ze allemaal. Laat maar zien: één training, dan praten we verder.";
  }

  if (!next) {
    return "Zonder plan ben je gewoon wat aan het rondlopen, jong. Kom naar mijn hoek, dan maken we er een.";
  }

  if (sleep?.is_recent && sleep.recovery?.status === "LOW") {
    return "Je lijf is nog niet hersteld, dat zie ik aan je nacht. Doe vandaag rustig, of schuif je training op.";
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

function heroPanel(next, estimate, sleep) {
  const coach = coachDialog(coachLine(next, estimate, sleep)).element;

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

export async function overview() {
  const [gear, workouts, plan, estimate, sleep] = await Promise.all([
    api("/api/equipment/"),
    api("/api/workouts/?limit=30"),
    api(`/api/plans/active`),
    api(`/api/analytics/estimates`),
    api(`/api/analytics/sleep`),
  ]);

  const fitness = estimate.fitness;

  return [
    h("div", { class: "home-grid" },
      h("div", {},
        heroPanel(nextSession(plan), estimate, sleep),
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
        gear.filter((item) => item.needs_replacing).map((item) =>
          h("a", { class: "message gear-notice", href: "#profiel" },
            `${item.name} is op ${kilometers(item.kilometers * 1000)}: tijd om te vervangen.`)),
        sleep.is_recent && nightPanel(sleep),
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

const RECOVERY_ESTIMATE = {
  GOOD: "Goed hersteld",
  OK: "Redelijk hersteld",
  LOW: "Nog niet hersteld",
};

// Polar's six levels of Nightly Recharge.
const RECHARGE_LABELS = {
  1: "Zeer slecht",
  2: "Slecht",
  3: "Verminderd",
  4: "OK",
  5: "Goed",
  6: "Zeer goed",
};

function recoveryLabel(recovery) {
  return recovery.source === "POLAR"
    ? `Nightly Recharge: ${RECHARGE_LABELS[recovery.recharge_status]}`
    : `${RECOVERY_ESTIMATE[recovery.status]} (schatting)`;
}

function nightPanel(sleep) {
  const night = sleep.last_night;
  const recovery = sleep.recovery;

  return h("section", { class: "card night-card" },
    art("sleep"),
    h("div", {},
      h("h2", { style: "margin:0" }, "Afgelopen nacht"),
      h("p", { style: "margin:0" },
        [
          night.asleep_seconds ? duration(night.asleep_seconds) : null,
          night.sleep_score !== null ? `slaapscore ${night.sleep_score}` : null,
        ].filter(Boolean).join(" · ")),
      recovery && h("span", { class: `recovery-pill ${recovery.status.toLowerCase()}` }, recoveryLabel(recovery))
    )
  );
}
