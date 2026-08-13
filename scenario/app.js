const worker = new Worker("./worker.mjs", { type: "module" });
let snapshot;
