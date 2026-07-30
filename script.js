"use strict";
const teams={
  growth:{title:"Growth",outcome:"Sharper offers, campaigns, research, and launch plans.",agents:"MARK · DUSTIN · PAM · JIM"},
  build:{title:"Build",outcome:"Production workflows, integrations, automation, and ML.",agents:"BOB · LEO · HAL · DAVE"},
  models:{title:"Language + Research",outcome:"Retrieval, analysis, evaluation, and high-quality content.",agents:"JAN · STEVE · NEIL · CARL"},
  ops:{title:"Operations",outcome:"Reliable deployment, monitoring, reporting, and iteration.",agents:"TED · JOHN"},
  trust:{title:"Trust",outcome:"Security review, red-team testing, risk, and compliance support.",agents:"BENICIO · JOSH · BILLY · VERONICA"}
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
