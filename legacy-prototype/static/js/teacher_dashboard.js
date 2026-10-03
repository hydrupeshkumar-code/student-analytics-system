async function loadTeacherCharts(){
  const r=await fetch(window.analyticsEndpoint); const d=await r.json();
  const base={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}};
  new Chart(document.getElementById('subjectChart'),{type:'bar',data:{labels:d.subject_labels,datasets:[{data:d.subject_avgs,borderRadius:8}]},options:{...base,scales:{y:{beginAtZero:true,max:100}}}});
  new Chart(document.getElementById('gradeChart'),{type:'doughnut',data:{labels:d.grade_labels,datasets:[{data:d.grade_values}]},options:{responsive:true,maintainAspectRatio:false}});
  new Chart(document.getElementById('scatterChart'),{type:'scatter',data:{datasets:[{label:'Students',data:d.scatter.map(x=>({x:x.attendance,y:x.marks})),pointRadius:5}]},options:{...base,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>{const x=d.scatter[c.dataIndex];return `${x.name}: ${x.attendance}% attendance, ${x.marks}% marks`;}}}},scales:{x:{title:{display:true,text:'Attendance %'},min:0,max:100},y:{title:{display:true,text:'Marks %'},min:0,max:100}}}});
  new Chart(document.getElementById('trendChart'),{type:'line',data:{labels:d.exam_labels,datasets:[{data:d.exam_values,tension:.35,fill:false,borderWidth:3,pointRadius:4}]},options:{...base,scales:{y:{beginAtZero:true,max:100}}}});
}
loadTeacherCharts().catch(e=>console.error(e));
