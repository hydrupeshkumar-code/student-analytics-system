let charts={};
async function loadAnalytics(){
  const qs=new URLSearchParams();
  const ids=['filterDepartment','filterSemester','filterSection','filterSubject'];
  ids.forEach(id=>{const v=document.getElementById(id)?.value;if(v) qs.set(id.replace('filter','').toLowerCase().replace('department','department').replace('semester','semester').replace('section','section').replace('subject','subject_id'),v);});
  // Normalize generated keys explicitly.
  qs.delete('subject');
  const subj=document.getElementById('filterSubject')?.value; if(subj) qs.set('subject_id',subj);
  const res=await fetch(`${window.analyticsEndpoint}?${qs}`); const d=await res.json();
  document.getElementById('classAverage').textContent=`${d.class_average}%`;
  Object.values(charts).forEach(c=>c.destroy());
  const opts={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}};
  charts.subject=new Chart(document.getElementById('aSubject'),{type:'bar',data:{labels:d.subject_labels,datasets:[{data:d.subject_avgs,borderRadius:8}]},options:{...opts,scales:{y:{beginAtZero:true,max:100}}}});
  charts.att=new Chart(document.getElementById('aAttendance'),{type:'bar',data:{labels:d.attendance_labels,datasets:[{data:d.attendance_values,borderRadius:8}]},options:{...opts,scales:{y:{beginAtZero:true,max:100}}}});
  charts.grade=new Chart(document.getElementById('aGrade'),{type:'doughnut',data:{labels:d.grade_labels,datasets:[{data:d.grade_values}]},options:{responsive:true,maintainAspectRatio:false}});
  charts.trend=new Chart(document.getElementById('aTrend'),{type:'line',data:{labels:d.exam_labels,datasets:[{data:d.exam_values,tension:.35,borderWidth:3}]},options:{...opts,scales:{y:{beginAtZero:true,max:100}}}});
  charts.scatter=new Chart(document.getElementById('aScatter'),{type:'scatter',data:{datasets:[{data:d.scatter.map(x=>({x:x.attendance,y:x.marks})),pointRadius:6}]},options:{...opts,scales:{x:{title:{display:true,text:'Attendance %'},min:0,max:100},y:{title:{display:true,text:'Marks %'},min:0,max:100}},plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>{const x=d.scatter[c.dataIndex];return `${x.name}: ${x.attendance}% / ${x.marks}%`;}}}}}});
}
document.querySelectorAll('#filterDepartment,#filterSemester,#filterSection,#filterSubject').forEach(el=>el.addEventListener('change',loadAnalytics));
document.getElementById('filterSection')?.addEventListener('input',()=>{clearTimeout(window.__saTimer);window.__saTimer=setTimeout(loadAnalytics,300)});
document.getElementById('resetFilters')?.addEventListener('click',()=>{['filterDepartment','filterSemester','filterSection','filterSubject'].forEach(id=>document.getElementById(id).value='');loadAnalytics()});
loadAnalytics().catch(e=>console.error(e));
