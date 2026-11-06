"use strict";

/* Pictures and their movement. The images come from Fluent Emoji and Noto
   Animated Emoji, see assets/CREDITS.md. Movement is in style.css and stops for
   people who ask for reduced motion. */

const SPORT_IMAGES = {
  RUNNING: "running",
  CYCLING: "cycling",
  SWIMMING: "swimming",
  STRENGTH: "strength",
  OTHER: "other",
};

const ANIMATED = {
  fire: "fire",
  trophy: "trophy",
  party: "party",
};

const reducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function picture(name, className = "", alt = "") {
  const image = document.createElement("img");

  image.src = `assets/${name}.png`;
  image.alt = alt;
  image.decoding = "async";

  if (className) image.className = className;

  return image;
}

// A moving image, or the still version for reduced motion.
function animatedPicture(name, className) {
  const holder = document.createElement("picture");
  const still = document.createElement("source");
  const image = picture(name, className);

  still.media = "(prefers-reduced-motion: reduce)";
  still.srcset = `assets/${name}.png`;
  image.src = `assets/${ANIMATED[name]}-animated.webp`;
  image.loading = "lazy";

  holder.append(still, image);

  return holder;
}

function decoration(className) {
  const part = document.createElement("span");
  part.className = className;
  return part;
}

// A figure with movement around it, as a scene for one sport.
function sportScene(sport) {
  const scene = document.createElement("div");

  scene.className = `scene scene-${SPORT_IMAGES[sport]}`;
  scene.setAttribute("aria-hidden", "true");
  scene.append(decoration("glow"));

  if (sport === "OTHER") scene.append(picture("mountain", "backdrop"));

  if (sport === "RUNNING" || sport === "CYCLING") {
    for (let index = 1; index <= 3; index += 1) {
      scene.append(decoration(`speed-line speed-line-${index}`));
    }
  }

  if (sport !== "SWIMMING") scene.append(decoration("ground"));

  scene.append(decoration("shadow"), picture(SPORT_IMAGES[sport], "figure"));

  if (sport === "SWIMMING") {
    for (let index = 1; index <= 4; index += 1) {
      scene.append(decoration(`bubble bubble-${index}`));
    }
  }

  if (sport === "STRENGTH") {
    scene.append(decoration("spark spark-1"), decoration("spark spark-2"));
  }

  return scene;
}

function coachFigure() {
  const figure = document.createElement("div");

  figure.className = "coach-art";
  figure.append(
    picture("coach", "coach-head", "De Coach, een oude trainer"),
    picture("glove", "coach-glove")
  );

  return figure;
}

function art(name) {
  if (name === "coach") return coachFigure();
  if (name === "flame") return animatedPicture("fire", "flame-art");
  if (name === "trophy") return animatedPicture("trophy", "trophy-art");
  if (name === "party") return animatedPicture("party", "party-art");
  if (name === "calendar") return picture("calendar", "inline-icon");
  if (name.startsWith("icon_")) return picture(SPORT_IMAGES[name.slice(5)], "sport-icon");

  return sportScene(name);
}

// A speech bubble that types its text while the Coach talks along.
function coachDialog(text) {
  const figure = art("coach");
  const line = document.createElement("p");
  const name = document.createElement("strong");
  const bubble = document.createElement("div");
  const dialog = document.createElement("section");

  name.textContent = "Coach";
  bubble.className = "coach-message";
  bubble.append(name, line);
  dialog.className = "coach-dialog";
  dialog.append(figure, bubble);

  let typing = null;

  const say = (message) => {
    clearInterval(typing);

    if (reducedMotion()) {
      line.textContent = message;
      return;
    }

    // The untyped rest keeps its space, so the bubble does not grow while typing.
    const typed = document.createTextNode("");
    const untyped = document.createElement("span");

    untyped.className = "untyped";
    untyped.textContent = message;
    line.replaceChildren(typed, untyped);
    dialog.classList.add("talking");

    let shown = 0;

    typing = setInterval(() => {
      // Long answers should not keep the reader waiting.
      shown += message.length > 200 ? 5 : 1;
      typed.data = message.slice(0, shown);
      untyped.textContent = message.slice(shown);

      if (shown >= message.length) {
        clearInterval(typing);
        dialog.classList.remove("talking");
      }
    }, 20);
  };

  say(text);

  return { element: dialog, say };
}

const CONFETTI_COLORS = ["#6E0D25", "#FAAA8D", "#AFD2E9", "#00272B", "#93A8AC"];

function confetti(pieces = 70) {
  if (reducedMotion()) return;

  const layer = document.createElement("div");
  layer.className = "confetti";
  layer.setAttribute("aria-hidden", "true");

  for (let index = 0; index < pieces; index += 1) {
    const piece = document.createElement("i");

    piece.style.left = `${Math.random() * 100}%`;
    piece.style.background = CONFETTI_COLORS[index % CONFETTI_COLORS.length];
    piece.style.animationDelay = `${Math.random() * 0.6}s`;
    piece.style.animationDuration = `${1.6 + Math.random() * 1.4}s`;
    piece.style.setProperty("--spin", `${Math.random() * 900 - 450}deg`);
    piece.style.setProperty("--drift", `${Math.random() * 160 - 80}px`);

    layer.append(piece);
  }

  document.body.append(layer);
  setTimeout(() => layer.remove(), 3800);
}

// Counts a number up from zero the first time it appears.
function countUp(element, target, format) {
  if (reducedMotion() || target <= 0) {
    element.textContent = format(target);
    return;
  }

  const startedAt = performance.now();
  const length = 700;

  const step = (now) => {
    const progress = Math.min((now - startedAt) / length, 1);
    const eased = 1 - (1 - progress) ** 3;

    element.textContent = format(Math.round(target * eased));

    if (progress < 1 && element.isConnected) requestAnimationFrame(step);
  };

  element.textContent = format(0);
  requestAnimationFrame(step);
}
