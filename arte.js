// Arte do topo da tela Hoje: céu (fundo), estrelas animadas, lua com a fase real e ícones Meteocons (MIT, Bas Milius).
(function(){
  const ICONES='https://cdn.jsdelivr.net/gh/basmilius/weather-icons@2.0.0/production/fill/all/';
  const SINODICO=29.530588853, LUA_NOVA_REF=Date.UTC(2000,0,6,18,14);
  const faseLua=d=>((((d-LUA_NOVA_REF)/864e5)%SINODICO)+SINODICO)%SINODICO/SINODICO;
  const nomeFase=p=>['Lua nova','Lua crescente','Quarto crescente','Crescente gibosa','Lua cheia','Minguante gibosa','Quarto minguante','Lua minguante'][Math.round(p*8)%8];

  // Lua realista: disco com relevo suave + sombra do lado escuro. Hemisfério sul: a crescente acende à esquerda.
  function lua(p){
    const cx=100,cy=100,r=46,crescente=p<.5,q=crescente?p:1-p,c=Math.cos(2*Math.PI*q),rx=Math.abs(c)*r,sw=c>=0?0:1;
    const d=`M${cx} ${cy-r} A${r} ${r} 0 0 0 ${cx} ${cy+r} A${rx.toFixed(2)} ${r} 0 0 ${sw} ${cx} ${cy-r}Z`;
    return `<svg viewBox="0 0 200 200" class="lua"><defs>
      <radialGradient id="lg" cx="38%" cy="34%" r="75%"><stop offset="0" stop-color="#fffdf6"/><stop offset=".6" stop-color="#e6e2d6"/><stop offset="1" stop-color="#bcb7a8"/></radialGradient>
      <radialGradient id="lb"><stop offset="0" stop-color="#dfe8ff" stop-opacity=".42"/><stop offset=".55" stop-color="#9fb4ff" stop-opacity=".12"/><stop offset="1" stop-color="#9fb4ff" stop-opacity="0"/></radialGradient></defs>
      <circle cx="${cx}" cy="${cy}" r="96" fill="url(#lb)"/>
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#lg)"/>
      <circle cx="84" cy="86" r="8" fill="#000" opacity=".06"/><circle cx="114" cy="114" r="11" fill="#000" opacity=".05"/>
      <circle cx="110" cy="80" r="5" fill="#000" opacity=".07"/><circle cx="88" cy="118" r="6" fill="#000" opacity=".05"/><circle cx="124" cy="96" r="3.5" fill="#000" opacity=".06"/>
      <path d="${d}" fill="#141a36" fill-opacity=".94"${crescente?` transform="translate(${2*cx} 0) scale(-1 1)"`:''}/>
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#e3ebff" stroke-opacity=".22" stroke-width="1.2"/></svg>`;
  }
  function icone(nome,cls){return `<img class="${cls||'ic-arte'}" src="${ICONES}${nome}.svg" alt="">`}

  // Céu de cada situação, da tela inteira: cor viva no topo, escurecendo no mesmo tom até embaixo
  // (os cartões de vidro ficam por cima). A luz do sol ou da lua fica no canto da arte.
  function fundo(tipo){
    const F={
      sol:'radial-gradient(80% 40% at 82% 8%,rgba(255,220,150,.55),rgba(255,220,150,0) 70%),linear-gradient(180deg,#1d5cc8 0%,#3c86dc 22%,#2b6bb8 42%,#18396e 68%,#0c1630 100%)',
      aurora:'radial-gradient(90% 38% at 78% 12%,rgba(255,196,140,.6),rgba(255,196,140,0) 70%),linear-gradient(180deg,#22306e 0%,#5b4791 18%,#b36b8f 34%,#5a3e6e 56%,#24193d 78%,#0f0c1c 100%)',
      nuvem:'radial-gradient(80% 40% at 82% 8%,rgba(255,240,210,.28),rgba(255,240,210,0) 70%),linear-gradient(180deg,#47648f 0%,#6d87ab 22%,#4c6385 44%,#2a3854 70%,#121828 100%)',
      chuva:'linear-gradient(180deg,#2e3d57 0%,#4a5b76 22%,#35445e 44%,#1e2739 70%,#0d1119 100%)',
      noite:'radial-gradient(70% 36% at 80% 10%,rgba(160,180,255,.24),rgba(160,180,255,0) 70%),linear-gradient(180deg,#060a24 0%,#111a4a 24%,#1b2158 44%,#121638 70%,#080a18 100%)',
      noiteNuvem:'linear-gradient(180deg,#0e1430 0%,#1d2648 26%,#20284a 46%,#131833 72%,#080a16 100%)',
      temporal:'radial-gradient(80% 40% at 78% 6%,rgba(130,165,255,.2),rgba(130,165,255,0) 70%),linear-gradient(180deg,#0f1832 0%,#1e2b4b 26%,#1b2541 46%,#111729 72%,#080a12 100%)'};
    return F[tipo];
  }

  // arteTempo(codigoWMO, ehDia, data) → {html da arte, fundo do céu, quantas estrelas, chuva?, raio?, legenda}
  window.arteTempo=function(code,dia,data){
    data=data||new Date();
    const chuva=(code>=51&&code<=67)||(code>=80&&code<=82),temporal=code>=95,nevoa=code===45||code===48;
    let html='',tipo,estrelas=0,legenda='';
    const p=faseLua(data);
    if(temporal){html=icone(dia?'thunderstorms-day-rain':'thunderstorms-night-rain');tipo='temporal'}
    else if(chuva){html=icone(code<=57?'drizzle':code>=80?(dia?'partly-cloudy-day-rain':'partly-cloudy-night-rain'):'rain');tipo=dia?'chuva':'temporal'}
    else if(nevoa){html=icone(dia?'fog-day':'fog-night');tipo=dia?'nuvem':'noiteNuvem';estrelas=dia?0:30}
    else if(code===3){html=icone(dia?'overcast-day':'overcast-night');tipo=dia?'nuvem':'noiteNuvem';estrelas=dia?0:40}
    else if(code===2){
      if(dia){html=icone('partly-cloudy-day');tipo='sol'}
      else{html=lua(p)+icone('cloudy','ic-nuvem');tipo='noite';estrelas=110;legenda=nomeFase(p)}
    }else{
      if(dia){html=icone('clear-day');tipo='sol'}
      else{html=lua(p);tipo='noite';estrelas=180;legenda=`${nomeFase(p)} · ${Math.round((1-Math.cos(2*Math.PI*p))/2*100)}% iluminada`}
    }
    // Das 5h às 8h, céu limpo ou com poucas nuvens ganha a cor do amanhecer
    const h=data.getHours();
    if(tipo==='sol'&&h>=5&&h<8)tipo='aurora';
    return{html,fundo:fundo(tipo),tipo,estrelas,chuva:chuva||temporal,raio:temporal,legenda};
  };

  // Estrelas: tamanhos e brilhos variados, piscando; uma estrela cadente de vez em quando
  window.ceuEstrelado=function(canvas,n){
    const cx=canvas.getContext('2d'),dpr=devicePixelRatio||1;
    canvas.width=canvas.offsetWidth*dpr;canvas.height=canvas.offsetHeight*dpr;
    const W=canvas.width,H=canvas.height;
    const E=Array.from({length:n},()=>{const big=Math.random()<.08;return{x:Math.random()*W,y:Math.pow(Math.random(),1.4)*H*.85,
      r:(big?1.4+Math.random()*.9:.35+Math.random()*.8)*dpr,b:.35+Math.random()*.65,f:.4+Math.random()*1.6,o:Math.random()*6.3,big}});
    let cadente=null,prox=performance.now()+3000+Math.random()*5000;
    (function quadro(t){
      cx.clearRect(0,0,W,H);
      for(const e of E){const a=e.b*(.55+.45*Math.sin(t/1000*e.f+e.o));cx.globalAlpha=a;cx.fillStyle='#fff';
        cx.beginPath();cx.arc(e.x,e.y,e.r,0,7);cx.fill();
        if(e.big){cx.globalAlpha=a*.25;cx.beginPath();cx.arc(e.x,e.y,e.r*3.2,0,7);cx.fill()}}
      if(!cadente&&t>prox){cadente={x:W*(.1+Math.random()*.6),y:H*(.05+Math.random()*.25),t0:t}}
      if(cadente){const k=(t-cadente.t0)/900;if(k>1){cadente=null;prox=t+6000+Math.random()*9000}else{
        const x=cadente.x+k*140*dpr,y=cadente.y+k*60*dpr,g=cx.createLinearGradient(x-70*dpr,y-30*dpr,x,y);
        g.addColorStop(0,'rgba(255,255,255,0)');g.addColorStop(1,`rgba(255,255,255,${(1-k)*.9})`);
        cx.globalAlpha=1;cx.strokeStyle=g;cx.lineWidth=1.4*dpr;cx.beginPath();cx.moveTo(x-70*dpr,y-30*dpr);cx.lineTo(x,y);cx.stroke()}}
      cx.globalAlpha=1;requestAnimationFrame(quadro);
    })(performance.now());
  };
  window.faseLua=faseLua;window.luaSVG=lua;window.nomeFase=nomeFase;
})();
