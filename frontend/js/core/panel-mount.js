/**
 * Standard dashboard panel lifecycle: collect elements → render on store → bind events → destroy.
 */
export function createPanelMount({ collectElements, render, bindEvents }) {
  if (typeof collectElements !== "function" || typeof render !== "function") {
    throw new Error("createPanelMount requires collectElements and render");
  }

  return function mountPanel(root, context) {
    const elements = collectElements(root);
    let destroyed = false;

    const runRender = (snapshot) => {
      if (destroyed) {
        return;
      }
      render(snapshot, elements, context);
    };

    const unbindEvents = bindEvents?.(elements, context, runRender) || (() => {});

    runRender(context.store.getState());
    const unsubscribe = context.store.subscribe(runRender);

    return () => {
      destroyed = true;
      unsubscribe();
      unbindEvents();
    };
  };
}
