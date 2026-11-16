const s=document.querySelector('#stage'),c=document.querySelector('#controls'),m=document.querySelector('#msg');
s.innerHTML='<canvas id="x"></canvas>';let x=document.querySelector('#x'),q=x.getContext('2d');
x.width=900;x.height=360;let temp=.5;
function draw(){q.clearRect(0,0,900,360);for(let i=0;i<24;i++){let px=50+(i*83)%800,py=60+(i*47)%240;let dx=Math.sin(i*7)*40*temp,dy=Math.cos(i*5)*30*temp;q.beginPath();q.arc(px+dx,py+dy,7,0,7);q.fill()}m.textContent='Temperature = '+temp.toFixed(1);}
let r=document.createElement('input');r.type='range';r.min=.1;r.max=2;r.step=.1;r.value=temp;r.oninput=()=>{temp=+r.value;AASHA.emit('parameter_change',{temperature:temp});draw()};c.append('Temperature ',r);draw();