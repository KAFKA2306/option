import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.mjs";

const runtime = loadPyodide();

self.onmessage = async (event) => {
  const pyodide = await runtime;
  self.postMessage({ id: event.data?.id, ready: Boolean(pyodide) });
};
