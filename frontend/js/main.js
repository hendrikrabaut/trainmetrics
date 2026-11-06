import { api } from "./api.js";
import { message } from "./dom.js";
import { refreshGame } from "./gamification.js";
import { route, setRouteHandler } from "./navigation.js";
import { coachView } from "./views/plan.js";
import { profileView, setupView } from "./views/profile.js";
import { statisticsView } from "./views/statistics.js";
import { overview } from "./views/today.js";
import { trainings } from "./views/trainings.js";
import { trophies } from "./views/trophies.js";

const app = document.getElementById("app");

const VIEWS = {
  vandaag: overview,
  trainingen: trainings,
  plan: coachView,
  statistieken: statisticsView,
  trofeeen: trophies,
  profiel: profileView,
};

let routeCounter = 0;

async function render() {
  const current = ++routeCounter;
  const name = location.hash.slice(1).split("?")[0];
  const view = VIEWS[name] ? name : "vandaag";

  document.querySelectorAll("[data-view]").forEach((link) => {
    if (link.dataset.view === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });

  try {
    if (!(await api("/api/profile/"))) {
      app.replaceChildren(...setupView());
      return;
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

setRouteHandler(render);
window.addEventListener("hashchange", route);
route();
