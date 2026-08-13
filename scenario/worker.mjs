import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.mjs";

const runtime = (async () => {
  const pyodide = await loadPyodide();
  const response = await fetch("../src/scenario_core.py", { cache: "no-store" });
  if (!response.ok) throw new Error(`scenario core load failed: ${response.status}`);
  pyodide.FS.writeFile("/scenario_core.py", await response.text());
  pyodide.runPython("import sys; sys.path.insert(0, '/')");
  return pyodide;
})();

self.onmessage = async (event) => {
  const { id, snapshot, overrides = {} } = event.data ?? {};
  try {
    const pyodide = await runtime;
    pyodide.globals.set("snapshot_json", JSON.stringify(snapshot));
    pyodide.globals.set("overrides_json", JSON.stringify(overrides));
    const resultJson = pyodide.runPython(`
import json
from scenario_core import calculate_scenario
json.dumps(calculate_scenario(json.loads(snapshot_json), json.loads(overrides_json)), allow_nan=False)
`);
    self.postMessage({ id, result: JSON.parse(resultJson) });
  } catch (error) {
    self.postMessage({ id, error: error instanceof Error ? error.message : String(error) });
  }
};
