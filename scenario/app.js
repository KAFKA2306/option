const worker = new Worker("./worker.mjs", { type: "module" });
const form = document.querySelector("form");
const output = document.querySelector("pre");
let snapshot;

fetch("./snapshot.json", { cache: "no-store" }).then((r) => r.json()).then((data) => {
  snapshot = data;
  document.querySelector("#as-of").textContent = data.observation_time;
  document.querySelector("#source").textContent = data.provenance.source_url;
});
worker.onmessage = (event) => {
  output.textContent = event.data.error ? `REJECTED: ${event.data.error}` : JSON.stringify(event.data.result, null, 2);
};
form.onsubmit = (event) => {
  event.preventDefault();
  const overrides = Object.fromEntries(new FormData(form).entries());
  if (overrides.contract_type.startsWith("PERPETUAL")) delete overrides.delivery_time;
  worker.postMessage({ id: 1, snapshot, overrides });
};
