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

  // Céu de cada situação, com a luz do sol ou da lua no canto da arte
  function fundo(tipo){
    const F={
      sol:'radial-gradient(70% 45% at 82% 12%,rgba(255,214,140,.55),rgba(255,214,140,0) 70%),linear-gradient(180deg,#1b56c4 0%,#3b86de 42%,#7db3ec 72%,rgba(125,179,236,0) 100%)',
      nuvem:'radial-gradient(70% 45% at 82% 12%,rgba(255,240,210,.25),rgba(255,240,210,0) 70%),linear-gradient(180deg,#45628f 0%,#6f88ad 45%,#93a7c4 72%,rgba(147,167,196,0) 100%)',
      chuva:'linear-gradient(180deg,#2c3a52 0%,#45556f 48%,#5d6c84 74%,rgba(93,108,132,0) 100%)',
      noite:'radial-gradient(60% 40% at 80% 14%,rgba(160,180,255,.22),rgba(160,180,255,0) 70%),linear-gradient(180deg,#060a22 0%,#0f1640 45%,#1c2257 74%,rgba(28,34,87,0) 100%)',
      noiteNuvem:'linear-gradient(180deg,#0e1430 0%,#1c2446 50%,#2a3256 74%,rgba(42,50,86,0) 100%)',
      temporal:'linear-gradient(180deg,#151a28 0%,#262d40 50%,#343c52 74%,rgba(52,60,82,0) 100%)'};
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
    return{html,fundo:fundo(tipo),estrelas,chuva:chuva||temporal,raio:temporal,legenda};
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
  window.faseLua=faseLua;
})();
