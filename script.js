"use strict";

const missionModes = {
  automation: {
    label: "Operations + Automation",
    keywords: ["automate","automation","workflow","manual","repetitive","operations","process","crm","follow-up","follow up","intake","onboarding","reporting","hours","save time"],
    agents: ["ALPHA","CONDUCTOR","BRIDGE","BOB","PULSE"],
    forks: ["n8n","Activepieces","Twenty","Dify","Ruflo"],
    outcome: "Map the current workflow, isolate the highest-friction steps, design the smallest supervised automation, and define measurable operating controls.",
    approval: "Human approval before external messages, record changes, payments, destructive actions, or production deployment.",
    plan: [
      "Capture the current-state workflow, inputs, outputs, owners, exceptions, and failure points.",
      "Rank automation candidates by repetition, business impact, implementation effort, and risk.",
      "Design a supervised future-state workflow with explicit handoff and rollback points.",
      "Prototype the smallest useful automation and test it with non-sensitive sample data.",
      "Measure time, quality, throughput, cost, and exceptions before expanding the scope."
    ]
  },
  research: {
    label: "Research + Validation",
    keywords: ["research","validate","market","idea","competitor","compare","trend","evidence","sources","investigate","opportunity","whether","worth building"],
    agents: ["ALPHA","ROSALIND","SCOUT","PAM","PULSE"],
    forks: ["Firecrawl","Onyx","open-notebook","Karakeep","MarkItDown"],
    outcome: "Build an evidence-backed research packet, test the core assumptions, identify contradictions, and convert findings into a decision-ready recommendation.",
    approval: "Human review before relying on uncertain claims, purchasing data, publishing findings, or making consequential decisions.",
    plan: [
      "Translate the objective into testable questions, assumptions, success criteria, and evidence requirements.",
      "Gather current primary and high-quality secondary sources while preserving provenance.",
      "Compare sources, surface disagreement, and separate verified facts from inference.",
      "Score the opportunity against user value, demand evidence, feasibility, cost, and risk.",
      "Return a concise recommendation with the next validation experiment and stop conditions."
    ]
  },
  build: {
    label: "Product + Engineering",
    keywords: ["build","website","app","software","code","api","integration","agent","llm","rag","model","database","deploy","prototype","mvp","architecture"],
    agents: ["ALPHA","FORGE","BRIDGE","BOB","EVAL","PROCURE"],
    forks: ["Dify","Langflow","Flowise","LiteLLM","vLLM","Supabase"],
    outcome: "Convert the goal into a scoped product, choose the minimum viable architecture, implement the highest-value path first, and validate before scaling complexity.",
    approval: "Human approval for credentials, production data access, paid infrastructure, deployments, and consequential system changes.",
    plan: [
      "Define the user, job-to-be-done, core workflow, acceptance criteria, constraints, and non-goals.",
      "Choose the simplest architecture that meets the requirements and reuse proven components where possible.",
      "Build the core vertical slice end-to-end before adding secondary features.",
      "Test functionality, failure modes, permissions, observability, and user experience.",
      "Ship behind a controlled rollout and use real usage evidence to drive the next iteration."
    ]
  },
  growth: {
    label: "Growth + Revenue",
    keywords: ["customer","customers","sales","marketing","seo","lead","leads","revenue","outreach","campaign","offer","conversion","audience","brand","profit","sell","distribution"],
    agents: ["ALPHA","SCOUT","CLOSER","MAYA","PULSE"],
    forks: ["open-seo","marketingskills","Agent-Reach","listmonk","Postiz"],
    outcome: "Identify the highest-probability customer segment, sharpen the offer, build a measurable acquisition path, and avoid scaling distribution before message-market fit is proven.",
    approval: "Human approval before outbound contact, publishing, ad spend, pricing changes, or customer commitments.",
    plan: [
      "Define the target customer, painful problem, current alternative, urgency, and measurable outcome.",
      "Research demand signals, competitors, channels, objections, and willingness-to-pay evidence.",
      "Package one clear offer with a specific entry point and low-friction proof mechanism.",
      "Run a small measurable acquisition test before automating or increasing volume.",
      "Review replies, conversion, CAC assumptions, and objections; refine the message before scaling."
    ]
  },
  security: {
    label: "Digital Exposure + Security",
    keywords: ["security","cyber","osint","exposure","footprint","domain","username","breach","vulnerability","risk","attack","pentest","audit","public digital","threat"],
    agents: ["ALPHA","BENICIO","BILLY","PAUL","SAM","EVAL"],
    forks: ["Sherlock","theHarvester","user-scanner","CrowdSec","Firecrawl"],
    outcome: "Identify authorized public exposure, prioritize defensive risk, preserve evidence, and produce a remediation plan without crossing permission boundaries.",
    approval: "Explicit authorization is required before any intrusive testing, credential use, exploitation, scanning outside owned scope, or system modification.",
    plan: [
      "Define the owned or explicitly authorized scope and prohibited actions before collection begins.",
      "Collect public-source exposure and defensive signals using the least intrusive methods available.",
      "Validate findings, remove false positives, and rank issues by likelihood, impact, and exploitability.",
      "Create a remediation checklist covering account hygiene, public exposure, access controls, and monitoring.",
      "Escalate any intrusive validation to a separately authorized security workflow with human approval."
    ]
  },
  career: {
    label: "Career + Opportunity",
    keywords: ["job","career","resume","role","roles","hiring","interview","skills","portfolio","upwork","freelance","freelancer","forward deployed","employment","application"],
    agents: ["ALPHA","SCOUT","CLOSER","SCRIBE","PAM"],
    forks: ["career-ops","ai-job-search","Firecrawl","Twenty","Agent-Reach"],
    outcome: "Match proven skills to the highest-fit opportunities, identify gaps that actually matter, and convert the search into a focused pipeline with measurable next actions.",
    approval: "Human approval before applications, outreach, profile edits, scheduling, or commitments made on the user’s behalf.",
    plan: [
      "Define the target role, constraints, preferred work, compensation range, and strongest evidence of capability.",
      "Map existing projects and skills to current role requirements and identify only high-impact gaps.",
      "Build a prioritized opportunity list using fit, urgency, upside, and application friction.",
      "Tailor proof-of-work, positioning, and outreach to the selected opportunity rather than sending generic applications.",
      "Track responses and interview signals, then iterate the positioning based on real market feedback."
    ]
  }
};

const form = document.querySelector("#mission-form");
const textarea = document.querySelector("#mission-text");
const result = document.querySelector("#mission-result");
const charCount = document.querySelector("#char-count");

function scoreMission(text) {
  const normalized = text.toLowerCase();
  const scores = Object.entries(missionModes).map(([key, mode]) => {
    const score = mode.keywords.reduce((total, keyword) => total + (normalized.includes(keyword) ? 2 : 0), 0);
    return { key, score };
  });
  scores.sort((a, b) => b.score - a.score);
  return scores[0].score > 0 ? scores[0].key : "research";
}

function cleanMission(text) {
  return text.replace(/\s+/g, " ").trim();
}

function renderBrief(missionText, modeKey) {
  const mode = missionModes[modeKey];
  const shortMission = missionText.length > 150 ? `${missionText.slice(0, 147)}...` : missionText;
  result.innerHTML = `
    <div class="result-ready">
      <div class="result-top"><small>ALPHA MISSION BRIEF</small><strong>READY FOR REVIEW</strong></div>
      <div class="status-row"><span class="status-dot"></span><span>Mission classified · team routed · first-pass plan generated locally</span></div>
      <h3 class="mission-name">${escapeHtml(shortMission)}</h3>
      <div class="brief-grid">
        <div class="brief-block"><small>MISSION MODE</small><strong>${mode.label}</strong></div>
        <div class="brief-block"><small>SPECIALIST TEAM</small><strong>${mode.agents.join(" · ")}</strong></div>
        <div class="brief-block"><small>CANDIDATE FORKS</small><p>${mode.forks.join(" · ")}</p></div>
        <div class="brief-block"><small>DESIRED OUTCOME</small><p>${mode.outcome}</p></div>
      </div>
      <ol class="plan-list">
        ${mode.plan.map((step, index) => `<li><span>0${index + 1}</span><div>${step}</div></li>`).join("")}
      </ol>
      <div class="brief-block"><small>HUMAN APPROVAL GATE</small><p>${mode.approval}</p></div>
      <div class="result-actions">
        <button class="ghost-button" type="button" id="copy-brief">Copy brief</button>
        <button class="ghost-button" type="button" id="download-brief">Download .txt</button>
        <button class="ghost-button" type="button" id="reset-mission">New mission</button>
      </div>
    </div>`;

  const briefText = createPlainTextBrief(missionText, mode);
  document.querySelector("#copy-brief").addEventListener("click", () => copyBrief(briefText));
  document.querySelector("#download-brief").addEventListener("click", () => downloadBrief(briefText));
  document.querySelector("#reset-mission").addEventListener("click", resetMission);
}

function createPlainTextBrief(missionText, mode) {
  return [
    "ALPHA MISSION BRIEF",
    "===================",
    `Mission: ${missionText}`,
    `Mode: ${mode.label}`,
    `Specialist team: ${mode.agents.join(", ")}`,
    `Candidate forks: ${mode.forks.join(", ")}`,
    "",
    "Desired outcome:",
    mode.outcome,
    "",
    "Execution plan:",
    ...mode.plan.map((step, index) => `${index + 1}. ${step}`),
    "",
    "Human approval gate:",
    mode.approval,
    "",
    "Generated by the ALPHA Mission Control browser demo. Validate assumptions and evidence before consequential action."
  ].join("\n");
}

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}

async function copyBrief(text) {
  const button = document.querySelector("#copy-brief");
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  } catch {
    button.textContent = "Copy unavailable";
  }
  setTimeout(() => { if (button) button.textContent = "Copy brief"; }, 1600);
}

function downloadBrief(text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "alpha-mission-brief.txt";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function resetMission() {
  textarea.value = "";
  charCount.textContent = "0 / 1200";
  result.innerHTML = `<div class="result-empty"><span class="pulse"></span><p>ALPHA is awaiting a mission.</p><small>Your browser will generate the first-pass mission brief locally.</small></div>`;
  textarea.focus();
}

form.addEventListener("submit", event => {
  event.preventDefault();
  const missionText = cleanMission(textarea.value);
  if (!missionText) return;
  const mode = scoreMission(missionText);
  result.innerHTML = `<div class="result-empty"><span class="pulse"></span><p>ALPHA is routing the mission...</p><small>Classifying objective and selecting the smallest useful specialist team.</small></div>`;
  window.setTimeout(() => renderBrief(missionText, mode), 420);
});

textarea.addEventListener("input", () => {
  charCount.textContent = `${textarea.value.length} / 1200`;
});

document.querySelectorAll("[data-example]").forEach(button => {
  button.addEventListener("click", () => {
    textarea.value = button.dataset.example;
    charCount.textContent = `${textarea.value.length} / 1200`;
    textarea.focus();
    document.querySelector("#mission").scrollIntoView({ behavior: "smooth", block: "start" });
  });
});
