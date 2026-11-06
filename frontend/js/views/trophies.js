import { yearPanel } from "./year.js";
import { art } from "../art.js";
import { h, table } from "../dom.js";
import { dayLabel } from "../format.js";
import { game, medal, playerPanel } from "../gamification.js";

export function trophies() {
  const earned = game.badges.filter((badge) => badge.earned_on).length;

  return [
    art("trophy"),
    h("h1", {}, "Trofeeën"),
    playerPanel(),
    yearPanel(),
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
