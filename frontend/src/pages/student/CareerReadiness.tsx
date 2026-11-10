import { useMemo, useState } from "react";
import { Card, Hero, Meter, Stat } from "../../components/ui";
import { useAuth } from "../../lib/auth";
import { useFetch } from "../../lib/hooks";

interface Course { id:number; code:string; name:string; components:Record<string,number|null>; cp_pct:number|null; attendance_risk:{value_pct:number|null}; }
const SKILLS = [
  { name:"Programming basics", keys:["practical","quiz"], advice:"Practise functions, loops and fixing errors. Share a small program you made." },
  { name:"Problem solving", keys:["quiz","practical"], advice:"Solve a few problems each week. Write down how you solved each one." },
  { name:"Building projects", keys:["assignment","practical"], advice:"Build one complete project. Add a short guide, pictures and a simple demo." },
  { name:"Consistency & attendance", keys:["attendance"], advice:"Attend remaining sessions and ask faculty about missed concepts." },
  { name:"Communication", keys:[], advice:"Practise a 60-second project explanation and write a concise weekly progress note." },
  { name:"Working with data", keys:["practical","assignment"], advice:"Practise getting information from a database and cleaning a small data file." },
];
export default function CareerReadiness(){
 const {user}=useAuth(); const {data}=useFetch<{courses:Course[]}>('/me/courses');
 const [role,setRole]=useState(()=>{try{return localStorage.getItem(`sp-role-${user?.id}`)||"Software Developer"}catch{return "Software Developer"}});
 const [self,setSelf]=useState<Record<string,number>>(()=>{try{return JSON.parse(localStorage.getItem(`sp-self-${user?.id}`)||"{}") as Record<string,number>}catch{return {}}});
 const courses=data?.courses.filter(c=>c.cp_pct!==null)||[];
 const score=(skill:typeof SKILLS[number])=>{if(!skill.keys.length)return null;const vals=courses.flatMap(c=>skill.keys.map(k=>k==="attendance"?c.attendance_risk?.value_pct:c.components?.[k])).filter((v):v is number=>v!==null&&v!==undefined);return vals.length?Math.round(vals.reduce((a,b)=>a+b,0)/vals.length):null};
 const assessed=SKILLS.map(s=>({ ...s, evidence:score(s), confidence:self[s.name]??3 }));
 const readiness=Math.round(assessed.reduce((a,s)=>a+(s.evidence??s.confidence*20),0)/assessed.length);
 const gaps=useMemo(()=>assessed.map(s=>({...s,gap:Math.max(0,70-(s.evidence??s.confidence*20))})).sort((a,b)=>b.gap-a.gap),[data,self]);
 function setConfidence(name:string,value:number){const next={...self,[name]:value};setSelf(next);try{localStorage.setItem(`sp-self-${user?.id}`,JSON.stringify(next))}catch{}}
 function setTarget(value:string){setRole(value);try{localStorage.setItem(`sp-role-${user?.id}`,value)}catch{}}
 return <div className="stack"><Hero title="Internship readiness" subtitle="A practical skill-gap view that combines academic evidence with your self-assessment. This is guidance, not a hiring prediction." />
 <Card><div className="form-grid"><label className="field"><span>Target internship / role</span><select className="input" value={role} onChange={e=>setTarget(e.target.value)}><option>Software Developer</option><option>Python Developer</option><option>Data Analyst</option><option>Web Developer</option><option>Machine Learning Intern</option></select></label><div><div className="small muted">Indicative readiness</div><div className="stat-value">{readiness}%</div><Meter value={readiness}/><div className="small muted">Based on available assessment evidence and confidence ratings.</div></div></div></Card>
 <div className="grid grid-3"><Stat label="Skills mapped" value={SKILLS.length}/><Stat label="Priority gaps" value={gaps.filter(s=>s.gap>=25).length} sub="Focus areas to work on"/><Stat label="Courses contributing" value={courses.length}/></div>
 <div className="section-title"><h2>Skill evidence and next steps</h2></div>
 <div className="grid grid-2">{assessed.map(s=><Card key={s.name} title={s.name} subtitle={s.evidence===null?"Self-assessment only":"Estimated from released course assessments"}><div className="spread"><strong>{s.evidence===null?"No direct evidence":`${s.evidence}% academic evidence`}</strong><span className="small muted">Confidence {s.confidence}/5</span></div><Meter value={s.evidence??s.confidence*20}/><label className="field" style={{marginTop:12}}><span>Your confidence (1 = beginner, 5 = confident)</span><input className="input" type="range" min="1" max="5" value={s.confidence} onChange={e=>setConfidence(s.name,Number(e.target.value))}/></label><p className="small">{s.advice}</p></Card>)}</div>
 <Card title="Your recommended focus" subtitle={`Prioritised for a ${role} pathway`}>{gaps.slice(0,3).map((s,i)=><div key={s.name} style={{padding:"10px 0",borderBottom:"1px solid var(--rule)"}}><strong>{i+1}. {s.name}</strong><p className="small muted" style={{margin:"4px 0 0"}}>{s.advice}</p></div>)}</Card>
 </div>
}
