const ROOT = "api/v1/bitcoin-derivatives";

const $ = (selector) => document.querySelector(selector);
const fmt = new Intl.NumberFormat("ja-JP", {maximumFractionDigits: 2});
const fmt0 = new Intl.NumberFormat("ja-JP", {maximumFractionDigits: 0});

function pct(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toFixed(digits)}%`;
}

function ratePct(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

function usd(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `$${fmt0.format(Number(value))}`;
}

function dateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Tokyo",
    timeZoneName: "short",
  }).format(date);
}

function deliveryDate(ms) {
  if (!Number.isFinite(Number(ms))) return "—";
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(Number(ms)));
}

function sign(value) {
  if (!Number.isFinite(value) || value === 0) return "flat";
  return value > 0 ? "positive" : "negative";
}

function deltaText(value, suffix = " pp", digits = 3) {
  if (!Number.isFinite(value)) return "—";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(digits)}${suffix}`;
}

function sparkline(svg, values) {
  const clean = values.filter(Number.isFinite);
  if (clean.length < 2) {
    svg.innerHTML = "";
    return;
  }
  const width = 600;
  const height = 110;
  const pad = 8;
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const range = max - min || 1;
  const points = clean.map((value, index) => {
    const x = pad + (index / (clean.length - 1)) * (width - pad * 2);
    const y = height - pad - ((value - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const zeroY = min <= 0 && max >= 0
    ? height - pad - ((0 - min) / range) * (height - pad * 2)
    : null;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = `${zeroY === null ? "" : `<line x1="0" x2="${width}" y1="${zeroY}" y2="${zeroY}"></line>`}<path d="M ${points.replaceAll(" ", " L ")}"></path>`;
}

function contractCard(contract) {
  const isPerp = contract.contract_type === "PERPETUAL";
  const main = isPerp ? pct(contract.perpetual_premium_pct) : pct(contract.annualized_delivery_basis_pct, 2);
  const mainLabel = isPerp ? "現物に対するpremium" : "年率換算delivery basis";
  const facts = isPerp ? [
    ["Funding rate", ratePct(contract.last_funding_rate)],
    ["Open interest", `${fmt.format(contract.open_interest)} BTC`],
    ["24h volume", `${fmt0.format(contract.volume_24h)} BTC`],
    ["Mark / index", `${usd(contract.mark_price)} / ${usd(contract.index_price)}`],
  ] : [
    ["Raw basis", pct(contract.delivery_basis_pct)],
    ["DTE", `${fmt.format(contract.days_to_maturity)} 日`],
    ["Delivery", deliveryDate(contract.delivery_date_ms)],
    ["Open interest", `${fmt.format(contract.open_interest)} BTC`],
  ];
  return `
    <article class="card contract-card">
      <div class="contract-meta">${contract.contract_type} · ${contract.status}</div>
      <h3>${contract.symbol}</h3>
      <div class="contract-main">${main}</div>
      <div class="contract-sub">${mainLabel}</div>
      <div class="fact-list">
        ${facts.map(([label, value]) => `<div class="fact"><span>${label}</span><strong>${value}</strong></div>`).join("")}
      </div>
    </article>`;
}

function latestPair(records, predicate) {
  const filtered = records.filter(predicate).sort((a, b) => a.date.localeCompare(b.date));
  return [filtered.at(-1), filtered.at(-2)];
}

async function load() {
  const [indexResponse, currentResponse, dailyResponse] = await Promise.all([
    fetch(`${ROOT}/index.json`, {cache: "no-store"}),
    fetch(`${ROOT}/current.json`, {cache: "no-store"}),
    fetch(`${ROOT}/daily.json`, {cache: "no-store"}),
  ]);
  for (const response of [indexResponse, currentResponse, dailyResponse]) {
    if (!response.ok) throw new Error(`${response.url} returned HTTP ${response.status}`);
  }
  const [index, current, daily] = await Promise.all([
    indexResponse.json(),
    currentResponse.json(),
    dailyResponse.json(),
  ]);

  const contracts = current.contracts || [];
  const perpetual = contracts.find((row) => row.contract_type === "PERPETUAL");
  const deliveries = contracts
    .filter((row) => row.contract_type !== "PERPETUAL")
    .sort((a, b) => Number(a.days_to_maturity) - Number(b.days_to_maturity));
  if (!perpetual) throw new Error("active PERPETUAL contract is missing");

  $("#asof").textContent = `観測 ${dateTime(current.observed_at)} · canonical dataset ${index.coverage.perpetual_day_count}日 · raw evidence ${index.coverage.raw_evidence_count} objects`;
  $("#spot").textContent = usd(perpetual.spot_mid);
  $("#premium").textContent = pct(perpetual.perpetual_premium_pct);
  $("#funding").textContent = ratePct(perpetual.last_funding_rate);
  $("#open-interest").textContent = `${fmt0.format(perpetual.open_interest)} BTC`;

  $("#contracts").innerHTML = [perpetual, ...deliveries].map(contractCard).join("");

  const records = daily.records || [];
  const [latestPerp, previousPerp] = latestPair(records, (row) => row.contract_type === "PERPETUAL");
  if (!latestPerp || !previousPerp) throw new Error("at least two complete PERPETUAL days are required");
  const premiumDelta = Number(latestPerp.perpetual_premium_pct) - Number(previousPerp.perpetual_premium_pct);
  const fundingDelta = (Number(latestPerp.funding_rate_sum) - Number(previousPerp.funding_rate_sum)) * 100;

  const premiumDeltaEl = $("#premium-delta");
  premiumDeltaEl.dataset.sign = sign(premiumDelta);
  premiumDeltaEl.innerHTML = `${deltaText(premiumDelta)}<small>${previousPerp.date} → ${latestPerp.date} の日次close差</small>`;
  const fundingDeltaEl = $("#funding-delta");
  fundingDeltaEl.dataset.sign = sign(fundingDelta);
  fundingDeltaEl.innerHTML = `${deltaText(fundingDelta, " pp", 4)}<small>1日funding合計の差。annualized basisではありません</small>`;

  const perp30 = records
    .filter((row) => row.contract_type === "PERPETUAL")
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-30);
  sparkline($("#premium-chart"), perp30.map((row) => Number(row.perpetual_premium_pct)));
  $("#premium-chart-meta").textContent = `${perp30.at(0)?.date ?? "—"} → ${perp30.at(-1)?.date ?? "—"} · daily close`;

  const nearestSymbol = deliveries[0]?.symbol;
  const delivery30 = nearestSymbol ? records
    .filter((row) => row.symbol === nearestSymbol && row.annualized_delivery_basis_pct !== null)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-30) : [];
  sparkline($("#delivery-chart"), delivery30.map((row) => Number(row.annualized_delivery_basis_pct)));
  $("#delivery-chart-meta").textContent = nearestSymbol
    ? `${nearestSymbol} · actual DTEで年率換算`
    : "active delivery contractなし";

  $("#coverage").textContent = `${index.coverage.funding_event_count} funding events · ${index.coverage.perpetual_day_count} perpetual days · ${index.coverage.delivery_day_count} delivery days`;
  $("#status").textContent = "";
}

load().catch((error) => {
  const status = $("#status");
  status.className = "card notice error";
  status.innerHTML = `<strong>Canonical dataを表示できません</strong><p>${error.message}</p>`;
  for (const id of ["spot", "premium", "funding", "open-interest"]) $(id).textContent = "—";
  $("#contracts").innerHTML = "";
});
