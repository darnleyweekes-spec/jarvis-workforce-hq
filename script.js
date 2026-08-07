"use strict";
const teams={
  growth:{title:"Growth",outcome:"Research demand, package the offer, create launch assets, write sales copy, and audit conversion quality.",agents:"SCOUT · MAKER · CLOSER · ECHO · JUDGE"},
  strategy:{title:"Strategy",outcome:"Prioritize use cases, define ROI, product scope, governance, and the operating roadmap.",agents:"MARK · DUSTIN · PAM · JIM"},
  build:{title:"Build",outcome:"Design practical automations, integrations, application logic, ML workflows, and implementation plans.",agents:"BOB · LEO · HAL · DAVE"},
  models:{title:"Language + Research",outcome:"RAG, evaluation, model research, NLP workflows, retrieval, and evidence-backed analysis.",agents:"JAN · STEVE · NEIL · CARL"},
  ops:{title:"Operations",outcome:"Deployment, monitoring, CI/CD, reliability, measurement, and continuous improvement.",agents:"TED · JOHN"},
  trust:{title:"Trust",outcome:"Security review, adversarial testing, risk controls, policy, compliance, and escalation support.",agents:"BENICIO · JOSH · BILLY · VERONICA"}
};
document.querySelectorAll("[data-team]").forEach(button=>button.addEventListener("click",()=>{
  document.querySelectorAll("[data-team]").forEach(item=>{item.classList.remove("active");item.setAttribute("aria-selected","false")});
  button.classList.add("active");button.setAttribute("aria-selected","true");
  const team=teams[button.dataset.team];
  document.querySelector("#team-title").textContent=team.title;
  document.querySelector("#team-outcome").textContent=team.outcome;
  document.querySelector("#team-agents").textContent=team.agents;
}));
const hours=document.querySelector("#hours"),cost=document.querySelector("#cost"),rate=document.querySelector("#rate");
function update(){
  const h=Number(hours.value),c=Number(cost.value),r=Number(rate.value);
  const annual=h*52*(r/100);
  document.querySelector("#hours-value").textContent=`${h} hours`;
  document.querySelector("#cost-value").textContent=`$${c}/hr`;
  document.querySelector("#rate-value").textContent=`${r}%`;
  document.querySelector("#annual-hours").textContent=Math.round(annual).toLocaleString();
  document.querySelector("#capacity-value").textContent=`$${Math.round(annual*c).toLocaleString()}`;
  document.querySelector("#monthly-hours").textContent=Math.round(annual/12).toLocaleString();
}
[hours,cost,rate].forEach(input=>input.addEventListener("input",update));update();
