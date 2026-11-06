// Views ask for a redraw through here, so they need not know about the router.
let handler = () => {};

export function setRouteHandler(next) {
  handler = next;
}

export function route() {
  return handler();
}
