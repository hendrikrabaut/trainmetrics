"use strict";

/* Icons, rewards and maps. See assets/CREDITS.md for where they come from.
   Only rewards move, and they stop for people who ask for reduced motion. */

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

// A moving reward, or the still version for reduced motion.
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

// A one-color icon. The color comes from CSS, through a mask.
function glyph(name, className = "") {
  const icon = document.createElement("span");

  icon.className = `glyph ${className}`.trim();
  icon.style.setProperty("--icon", `url("assets/icons/${name}.svg")`);
  icon.setAttribute("aria-hidden", "true");

  return icon;
}

function art(name) {
  if (name === "coach") return coachFigure();
  if (name === "flame") return animatedPicture("fire", "flame-art");
  if (name === "trophy") return animatedPicture("trophy", "trophy-art");
  if (name === "party") return animatedPicture("party", "party-art");
  if (name === "calendar") return glyph("calendar", "inline-icon");
  if (name === "map") return glyph("map", "inline-icon");
  if (name === "sleep") return glyph("sleep", "sleep-art");
  if (name.startsWith("icon_")) return glyph(SPORT_IMAGES[name.slice(5)], "sport-icon");

  return glyph(SPORT_IMAGES[name], "scene");
}

function coachFigure() {
  const figure = document.createElement("div");

  figure.className = "coach-art";
  figure.append(glyph("coach"));

  return figure;
}

// What the Coach says. say() replaces it, for example with an answer from the model.
function coachDialog(text) {
  const line = document.createElement("p");
  const name = document.createElement("strong");
  const bubble = document.createElement("div");
  const dialog = document.createElement("section");

  line.setAttribute("aria-live", "polite");
  line.textContent = text;
  name.textContent = "Coach";
  bubble.className = "coach-message";
  bubble.append(name, line);
  dialog.className = "coach-dialog";
  dialog.append(coachFigure(), bubble);

  return {
    element: dialog,
    say: (message) => { line.textContent = message; },
  };
}

// Leaflet is only loaded when someone asks for a map.
let leafletLoading = null;

function loadLeaflet() {
  leafletLoading ??= new Promise((resolve, reject) => {
    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = "vendor/leaflet/leaflet.css";
    document.head.append(style);

    const script = document.createElement("script");
    script.src = "vendor/leaflet/leaflet.js";
    script.onload = () => resolve(window.L);
    script.onerror = () => reject(new Error("De kaart kon niet laden"));
    document.head.append(script);
  });

  return leafletLoading;
}

// With many routes, opens on where most of them start. One trip abroad should
// not zoom the whole map out; that route is still there when you zoom out.
function homeBounds(L, routes) {
  if (routes.length < 2) return null;

  const middle = (values) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
  const latitude = middle(routes.map((route) => route.points[0][0]));
  const longitude = middle(routes.map((route) => route.points[0][1]));

  const nearby = routes.filter((route) =>
    Math.abs(route.points[0][0] - latitude) < 0.6
    && Math.abs(route.points[0][1] - longitude) < 0.9);

  const bounds = L.latLngBounds([]);

  for (const route of nearby) bounds.extend(route.points);

  return bounds.isValid() ? bounds : null;
}

const MAP_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>';

// Draws routes on a map. Each route is { points, label }.
async function drawRoutes(element, routes, { markEnds = false } = {}) {
  const L = await loadLeaflet();
  const map = L.map(element, { scrollWheelZoom: false });

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: MAP_ATTRIBUTION,
    referrerPolicy: "strict-origin-when-cross-origin",
  }).addTo(map);

  const bounds = L.latLngBounds([]);

  for (const route of routes) {
    const line = L.polyline(route.points, {
      color: "#6E0D25",
      weight: markEnds ? 4 : 3,
      opacity: markEnds ? 0.95 : 0.55,
    }).addTo(map);

    if (route.label) {
      // Set as text, so nothing in a label can become markup.
      const label = document.createElement("span");
      label.textContent = route.label;
      line.bindPopup(label);
    }

    bounds.extend(line.getBounds());
  }

  if (markEnds && routes[0]) {
    const points = routes[0].points;
    const dot = (point, fill) => L.circleMarker(point, {
      radius: 6, color: "#FFFFFF", weight: 2, fillColor: fill, fillOpacity: 1,
    }).addTo(map);

    dot(points[0], "#00272B");
    dot(points.at(-1), "#FAAA8D");
  }

  map.fitBounds(homeBounds(L, routes) ?? bounds, { padding: [20, 20] });

  return map;
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
