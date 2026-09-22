"use strict";

const assert = require("node:assert/strict");
const { evaluateBrandIdentity } = require("./brand-identity-gate");

const blocked = evaluateBrandIdentity({ desiredIdentity: "professional" });
assert.equal(blocked.status, "EVIDENCE_REQUIRED");
assert.ok(blocked.missing.some(item => item.startsWith("currentImageEvidence")));

const ready = evaluateBrandIdentity({
  currentImageEvidence: [{
    verbatim: "The monitor alerted us, but we still had to work out what customers needed to hear.",
    source: "pilot interview notes",
    observedAt: "2026-09-20",
    touchpoint: "founder interview"
  }],
  currentImageSummary: "Another monitoring dashboard",
  desiredIdentity: "The evidence and incident-communication layer for small technical teams",
  gap: "The product is mistaken for the monitors it is designed to interpret",
  gapCause: "The first screen leads with monitoring language before the evidence-to-message workflow",
  perspectives: [{
    name: "product",
    gapLink: "The gap appears in what buyers think the product does",
    identityMeaning: "Interpret evidence, map impact, and prepare approved communication"
  }],
  benefits: {
    functional: "Turns provider alerts into an evidence ledger and three reviewed incident drafts",
    emotional: "Gives a small team confidence that it can communicate clearly under pressure",
    selfExpressive: "Choosing it signals disciplined, transparent incident handling"
  },
  strongestBenefit: "Gives a small team confidence that it can communicate clearly under pressure",
  exactMove: {
    location: "PrimeSignal homepage hero",
    action: "Show the alert-to-evidence-to-approved-message workflow before feature cards",
    stopDoing: "Stop describing PrimeSignal as if it were another uptime monitor"
  },
  oneMonthEvidence: {
    metric: "Qualified visitors who correctly describe PrimeSignal after viewing the hero",
    source: "five-second test plus sales-call notes",
    owner: "Darnley",
    target: "At least 8 of 10 say evidence or incident communication without prompting",
    windowDays: 30
  }
});

assert.equal(ready.status, "READY_FOR_HUMAN_REVIEW");
assert.equal(ready.exactMove.location, "PrimeSignal homepage hero");
console.log("brand identity gate tests passed");

