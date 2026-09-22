"use strict";

const PERSPECTIVES = new Set(["product", "organization", "person", "symbol"]);
const VAGUE_IDENTITIES = new Set(["professional", "innovative", "authentic", "better", "trusted"]);

function present(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function evidenceIsUsable(item) {
  return item && present(item.verbatim) && present(item.source) && present(item.observedAt) && present(item.touchpoint);
}

function evaluateBrandIdentity(input = {}) {
  const missing = [];
  const evidence = Array.isArray(input.currentImageEvidence) ? input.currentImageEvidence : [];

  if (!evidence.some(evidenceIsUsable)) {
    missing.push("currentImageEvidence: add at least one verbatim customer/prospect observation with source, date, and touchpoint");
  }
  if (!present(input.currentImageSummary)) missing.push("currentImageSummary");
  if (!present(input.desiredIdentity)) missing.push("desiredIdentity");
  if (present(input.desiredIdentity) && VAGUE_IDENTITIES.has(input.desiredIdentity.trim().toLowerCase())) {
    missing.push("desiredIdentity: replace the vague label with a specific reputation");
  }
  if (!present(input.gap)) missing.push("gap");
  if (!present(input.gapCause)) missing.push("gapCause");

  const perspectives = Array.isArray(input.perspectives) ? input.perspectives : [];
  if (perspectives.length < 1 || perspectives.length > 2) {
    missing.push("perspectives: choose one or two relevant perspectives");
  } else if (perspectives.some(item => !item || !PERSPECTIVES.has(item.name) || !present(item.gapLink) || !present(item.identityMeaning))) {
    missing.push("perspectives: each choice needs a valid name, gapLink, and identityMeaning");
  }

  const benefits = input.benefits || {};
  if (!present(benefits.functional)) missing.push("benefits.functional");
  if (!present(benefits.emotional) && !present(benefits.selfExpressive)) {
    missing.push("benefits: add a specific emotional or self-expressive benefit");
  }
  const benefitValues = [benefits.functional, benefits.emotional, benefits.selfExpressive].filter(present);
  if (!present(input.strongestBenefit) || !benefitValues.includes(input.strongestBenefit)) {
    missing.push("strongestBenefit: select one stated benefit exactly");
  }

  const move = input.exactMove || {};
  if (!present(move.location)) missing.push("exactMove.location");
  if (!present(move.action)) missing.push("exactMove.action");
  if (!present(move.stopDoing)) missing.push("exactMove.stopDoing");

  const measure = input.oneMonthEvidence || {};
  if (!present(measure.metric)) missing.push("oneMonthEvidence.metric");
  if (!present(measure.source)) missing.push("oneMonthEvidence.source");
  if (!present(measure.owner)) missing.push("oneMonthEvidence.owner");
  if (!present(measure.target)) missing.push("oneMonthEvidence.target");
  if (measure.windowDays !== 30) missing.push("oneMonthEvidence.windowDays: must equal 30");

  if (missing.length) {
    return {
      status: evidence.some(evidenceIsUsable) ? "INCOMPLETE" : "EVIDENCE_REQUIRED",
      missing,
      nextAction: evidence.some(evidenceIsUsable)
        ? "Complete only the missing fields; do not widen the scope."
        : "Collect real customer/prospect language before diagnosing the perception gap."
    };
  }

  return {
    status: "READY_FOR_HUMAN_REVIEW",
    currentImage: input.currentImageSummary.trim(),
    desiredIdentity: input.desiredIdentity.trim(),
    gap: input.gap.trim(),
    cause: input.gapCause.trim(),
    perspectives,
    benefits,
    strongestBenefit: input.strongestBenefit.trim(),
    exactMove: {
      location: move.location.trim(),
      action: move.action.trim(),
      stopDoing: move.stopDoing.trim()
    },
    oneMonthEvidence: measure,
    approvalGate: "A human must approve the move before publishing, outreach, pricing, or production changes."
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { evaluateBrandIdentity, evidenceIsUsable };
}

