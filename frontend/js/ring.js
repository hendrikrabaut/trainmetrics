import { h, svg } from "./dom.js";

// A share of a whole, drawn like the app icon. The stylesheet sets size and colors.
export function ring(part, whole, { label, center, size = "small", warning = false }) {
  const share = whole > 0 ? Math.min(1, Math.max(0, part / whole)) : 0;
  const circle = (name) => svg("circle", { class: name, cx: 50, cy: 50, r: 40, pathLength: 100 });
  const drawing = svg("svg", { viewBox: "0 0 100 100", "aria-hidden": "true" });

  drawing.append(circle("ring-track"));

  if (share > 0) {
    const fill = circle("ring-fill");
    fill.setAttribute("stroke-dasharray", `${share * 100} 100`);
    drawing.append(fill);
  }

  return h("div", {
    class: `ring ring-${size}${warning ? " warning" : ""}`,
    role: "progressbar",
    "aria-valuemin": 0,
    "aria-valuemax": whole,
    "aria-valuenow": Math.min(part, whole),
    "aria-label": label,
  }, drawing, center !== undefined && h("div", { class: "ring-center" }, center));
}
