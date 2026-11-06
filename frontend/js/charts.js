import { h, svg, table } from "./dom.js";
import { dayLabel, shortDay } from "./format.js";

function niceMax(value) {
  if (value <= 0) return 2;

  const magnitude = 10 ** Math.floor(Math.log10(value));

  // Even steps only, so the middle gridline is a whole number too. From ten
  // upwards, 12 and 16 also stay whole and keep the bars from looking small.
  const steps = magnitude >= 10 ? [1.2, 1.6, 2, 4, 6, 8, 10] : [2, 4, 6, 8, 10];

  for (const step of steps) {
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

function yAxis(root, width, ticks, scale, format, left = CHART.left) {
  for (const tick of ticks) {
    const y = scale(tick);

    root.append(svg("line", {
      class: "grid", x1: left, x2: width - CHART.right, y1: y, y2: y,
    }));

    const label = svg("text", { x: left - 8, y: y + 4, "text-anchor": "end" });
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

export function barChart(title, rows, { x, y, format, columns, tip = (row) => `Week van ${x(row)}` }) {
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

      const reveal = () => show(center, scale(value), format(value), tip(row));

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

export function lineChart(title, rows, { x, y, format, columns }) {
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

// Several lines over one numeric axis, with an optional dashed future part.
// series: [{ label, value, color }], with value(row) a number or null.
export function seriesChart(title, rows, { x, xFormat, series, format, marks = [], columns, projected = () => false }) {
  const draw = (width, show, hide) => {
    const root = svg("svg", { height: CHART.height, role: "img", "aria-label": title });
    const baseline = CHART.height - CHART.bottom;
    const right = width - CHART.right - (series.length > 1 ? 56 : 6);

    const positions = rows.map(x);
    const first = positions[0];
    const span = Math.max(positions.at(-1) - first, 1);

    const values = rows.flatMap((row) => series.map((line) => line.value(row))).filter((value) => value !== null);
    const low = Math.min(...values);
    const high = Math.max(...values);
    const padding = Math.max((high - low) * 0.1, Math.abs(high) * 0.02, 0.5);
    const yLow = low >= 0 ? Math.max(0, low - padding) : low - padding;
    const yHigh = high + padding;
    const yScale = (value) => baseline - ((value - yLow) / (yHigh - yLow)) * (baseline - CHART.top);

    const ticks = [yLow, (yLow + yHigh) / 2, yHigh];

    // Room for the longest label, such as "5:52 /km".
    const axis = Math.max(CHART.left, 16 + Math.max(...ticks.map((tick) => format(tick).length)) * 7);
    const left = axis + 4;
    const xScale = (value) => left + ((value - first) / span) * (right - left);

    yAxis(root, width, ticks, yScale, format, axis);

    if (yLow < 0 && yHigh > 0) {
      root.append(svg("line", {
        class: "zero-line", x1: axis, x2: width - CHART.right, y1: yScale(0), y2: yScale(0),
      }));
    }

    xLabel(root, Math.max(left + 14, xScale(positions[0])), xFormat(positions[0]));
    xLabel(root, Math.min(right - 16, xScale(positions.at(-1))), xFormat(positions.at(-1)));

    for (const mark of marks) {
      if (mark.x < first || mark.x > positions.at(-1)) continue;

      root.append(svg("line", {
        class: "chart-mark", x1: xScale(mark.x), x2: xScale(mark.x), y1: CHART.top, y2: baseline,
      }));

      const label = svg("text", { class: "chart-mark-label", x: xScale(mark.x) + 4, y: CHART.top + 10 });
      label.textContent = mark.label;
      root.append(label);
    }

    for (const line of series) {
      let path = "";
      let dashed = "";
      let previous = null;

      rows.forEach((row, index) => {
        const value = line.value(row);

        if (value === null) {
          previous = null;
          return;
        }

        const point = `${xScale(positions[index])},${yScale(value)}`;

        if (projected(row)) {
          dashed += `${previous ? (dashed ? "L" : `M${previous} L`) : "M"}${point} `;
        } else {
          path += `${previous ? "L" : "M"}${point} `;
        }

        previous = point;
      });

      root.append(svg("path", { d: path, fill: "none", stroke: line.color, "stroke-width": 2 }));

      if (dashed) {
        root.append(svg("path", {
          d: dashed, fill: "none", stroke: line.color, "stroke-width": 2, "stroke-dasharray": "5 4",
        }));
      }

    }

    // Labels at the end of each line, moved apart where the lines lie close.
    if (series.length > 1) {
      const labels = series
        .map((line) => {
          const last = [...rows].reverse().find((row) => line.value(row) !== null);
          return { text: line.label, y: yScale(line.value(last)) + 4 };
        })
        .sort((one, other) => one.y - other.y);

      labels.forEach((label, index) => {
        if (index && label.y - labels[index - 1].y < 13) label.y = labels[index - 1].y + 13;

        const element = svg("text", { class: "direct-label", x: right + 4, y: label.y });
        element.textContent = label.text;
        root.append(element);
      });
    }

    const crosshair = svg("line", { class: "crosshair", y1: CHART.top, y2: baseline, visibility: "hidden" });
    root.append(crosshair);

    const area = svg("rect", {
      class: "tracking-area", x: axis, y: CHART.top, width: right - axis, height: baseline - CHART.top,
    });

    area.addEventListener("pointermove", (event) => {
      const pointer = event.clientX - root.getBoundingClientRect().left;
      let closest = 0;

      positions.forEach((position, index) => {
        if (Math.abs(xScale(position) - pointer) < Math.abs(xScale(positions[closest]) - pointer)) closest = index;
      });

      const row = rows[closest];
      const place = xScale(positions[closest]);

      crosshair.setAttribute("x1", place);
      crosshair.setAttribute("x2", place);
      crosshair.setAttribute("visibility", "visible");

      show(
        place,
        CHART.top,
        series
          .filter((line) => line.value(row) !== null)
          .map((line) => (series.length > 1 ? `${line.label}: ${format(line.value(row))}` : format(line.value(row))))
          .join(" · "),
        xFormat(positions[closest])
      );
    });

    area.addEventListener("pointerleave", () => {
      crosshair.setAttribute("visibility", "hidden");
      hide();
    });

    root.append(area);

    return root;
  };

  return chartFigure(title, rows, columns, draw);
}
