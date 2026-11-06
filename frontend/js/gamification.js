import { api } from "./api.js";
import { art, confetti, picture } from "./art.js";
import { h } from "./dom.js";
import { decimal, percentage } from "./format.js";

export let game = null;

export function xpBar(part, whole, label) {
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

export function playerPanel() {
  const total = h("span", { class: "level-total" }, `${decimal(game.xp, 0)} XP`);

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

export function questPanel() {
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

export function showLevelUp(level, title) {
  const close = () => dialog.close();

  confetti();

  const dialog = h("dialog", { class: "level-up", onclose: () => dialog.remove() },
    art("party"),
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
export async function refreshGame() {
  const previous = game;

  game = await api(`/api/game/profile`);

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

export function medal(earned) {
  return picture("medal", `medal${earned ? " earned" : ""}`);
}
