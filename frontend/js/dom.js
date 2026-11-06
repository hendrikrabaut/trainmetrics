const SVG_NS = "http://www.w3.org/2000/svg";

// All text goes through textContent, so stored notes can never inject markup.
export function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);

  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;

    if (key.startsWith("on")) element.addEventListener(key.slice(2), value);
    else if (key === "class") element.className = value;
    else if (key === "value") element.value = value;
    else if (value === true) element.setAttribute(key, "");
    else element.setAttribute(key, value);
  }

  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    element.append(child);
  }

  return element;
}

export function svg(tag, attributes = {}) {
  const element = document.createElementNS(SVG_NS, tag);

  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }

  return element;
}

export function number(value) {
  return value === "" || value === null || value === undefined ? null : Number(value);
}

export function fields(form) {
  return Object.fromEntries(new FormData(form).entries());
}

export function message(text, isError = false) {
  return h("div", { class: `message${isError ? " error" : ""}`, role: "status" }, text);
}

// Runs a form submit and shows any error in the form instead of losing it.
export function submitter(handler) {
  return async (event) => {
    event.preventDefault();

    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");

    form.querySelector(":scope > .message")?.remove();

    if (button) button.disabled = true;

    try {
      await handler(form);
    } catch (error) {
      form.prepend(message(error.message, true));
    } finally {
      if (button) button.disabled = false;
    }
  };
}

export function table(columns, rows) {
  return h("div", { class: "table-wrap" },
    h("table", {},
      h("thead", {}, h("tr", {}, columns.map((column) => h("th", { scope: "col" }, column.label)))),
      h("tbody", {}, rows.map((row) =>
        h("tr", {}, columns.map((column) => h("td", {}, column.value(row))))
      ))
    )
  );
}

export function tile(value, label) {
  return h("div", { class: "tile" }, h("strong", {}, value), h("span", {}, label));
}

// Tabs inside a page. The choice survives a redraw of that page.
const chosenTabs = new Map();

export function subTabs(key, tabs) {
  const row = h("div", { class: "sub-tabs", role: "tablist" });
  const panels = tabs.map((tab) => h("div", { role: "tabpanel", hidden: true }, tab.content));

  const show = (label) => {
    chosenTabs.set(key, label);

    tabs.forEach((tab, index) => {
      panels[index].hidden = tab.label !== label;
      row.children[index].setAttribute("aria-selected", String(tab.label === label));
    });
  };

  for (const tab of tabs) {
    row.append(h("button", {
      type: "button",
      role: "tab",
      onclick: () => show(tab.label),
    }, tab.label));
  }

  const remembered = chosenTabs.get(key);

  show(tabs.some((tab) => tab.label === remembered) ? remembered : tabs[0].label);

  return h("div", {}, row, panels);
}
