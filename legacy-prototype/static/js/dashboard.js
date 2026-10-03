(function(){
  const root=document.documentElement;
  const saved=localStorage.getItem('sa-theme');
  if(saved) root.setAttribute('data-bs-theme',saved);
  function setTheme(){
    const next=root.getAttribute('data-bs-theme')==='dark'?'light':'dark';
    root.setAttribute('data-bs-theme',next); localStorage.setItem('sa-theme',next);
  }
  document.getElementById('themeToggle')?.addEventListener('click',setTheme);
  document.getElementById('themeTogglePage')?.addEventListener('click',setTheme);
  document.getElementById('sidebarToggle')?.addEventListener('click',()=>document.getElementById('sidebar')?.classList.toggle('open'));
  document.querySelectorAll('.sidebar .nav-link').forEach(link=>{ if(link.href===location.href) link.classList.add('active'); });
})();
