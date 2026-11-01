/* Synchronized source/keyed playback with a keyboard-accessible comparison wipe. */
function createWipeComparison({jobId,file,metadata,position=50,onPosition=()=>{}}){
 const element=document.createElement('section');element.className='wipe-player';
 const stage=document.createElement('div');stage.className='wipe-stage';
 const width=Number(metadata?.width)||16,height=Number(metadata?.height)||9;
 stage.style.aspectRatio=`${width} / ${height}`;
 const keyed=document.createElement('video'),source=document.createElement('video');
 for(const video of [keyed,source]){video.playsInline=true;video.preload='auto';video.muted=true;video.controls=false}
 keyed.className='wipe-keyed';source.className='wipe-source';
 const divider=document.createElement('div');divider.className='wipe-divider';divider.setAttribute('aria-hidden','true');
 const handle=document.createElement('span');handle.textContent='↔';divider.append(handle);
 const left=document.createElement('span'),right=document.createElement('span');
 left.className='wipe-label wipe-left';right.className='wipe-label wipe-right';left.textContent='Input';right.textContent='Keyed';
 const wipe=document.createElement('input');wipe.type='range';wipe.min='0';wipe.max='100';wipe.step='0.1';wipe.className='wipe-slider';wipe.setAttribute('aria-label','Input versus keyed wipe position');
 const validPosition=Number.isFinite(Number(position))?Math.min(100,Math.max(0,Number(position))):50;
 wipe.value=String(validPosition);
 function updateWipe(){stage.style.setProperty('--wipe',wipe.value+'%');wipe.setAttribute('aria-valuetext',`${Math.round(Number(wipe.value))}% input, ${100-Math.round(Number(wipe.value))}% keyed`)}
 wipe.addEventListener('input',()=>{updateWipe();onPosition(Number(wipe.value))});updateWipe();
 stage.append(keyed,source,divider,left,right,wipe);
 const controls=document.createElement('div');controls.className='wipe-controls';
 const play=document.createElement('button');play.type='button';play.textContent='Play';play.setAttribute('aria-label','Play comparison');
 const seek=document.createElement('input');seek.type='range';seek.min='0';seek.max='0';seek.step='0.001';seek.value='0';seek.disabled=true;seek.setAttribute('aria-label','Comparison playback position');
 const time=document.createElement('span');time.textContent='0:00 / 0:00';
 const feedback=document.createElement('p');feedback.className='muted wipe-feedback';feedback.setAttribute('role','status');
 const help=document.createElement('p');help.className='muted wipe-help';help.textContent='Drag the divider, or focus it and use the arrow keys. Playback and seeking stay synchronized. Input on the left; keyed checkerboard preview on the right.';
 controls.append(play,seek,time);element.append(stage,controls,help,feedback);
 let disposed=false,sourceMissing=false,frameRequest=null;
 const stamp=value=>{const seconds=Math.max(0,Math.floor(Number(value)||0));return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`};
 function synchronize(force=false){
  if(sourceMissing||source.readyState<1)return;
  const target=Math.min(keyed.currentTime,Math.max(0,source.duration-.001));
  if(Number.isFinite(target)&&(force||Math.abs(source.currentTime-target)>.05))source.currentTime=target;
  source.playbackRate=keyed.playbackRate;
 }
 function updateTime(){seek.value=String(keyed.currentTime);time.textContent=`${stamp(keyed.currentTime)} / ${stamp(keyed.duration)}`}
 function cancelFollow(){if(frameRequest!==null){if(keyed.cancelVideoFrameCallback)keyed.cancelVideoFrameCallback(frameRequest);else cancelAnimationFrame(frameRequest);frameRequest=null}}
 function follow(){frameRequest=null;if(disposed||keyed.paused)return;synchronize();frameRequest=keyed.requestVideoFrameCallback?keyed.requestVideoFrameCallback(follow):requestAnimationFrame(follow)}
 function pause(){keyed.pause();source.pause()}
 function playSource(){if(!sourceMissing)source.play().catch(error=>{if(!disposed&&!keyed.paused&&error.name!=='AbortError'){pause();feedback.textContent='Playback could not start. Press Play to retry.'}})}
 play.addEventListener('click',()=>{
  if(!keyed.paused){pause();return}
  if(keyed.ended)keyed.currentTime=0;
  synchronize(true);keyed.play().catch(error=>{if(!disposed&&error.name!=='AbortError')feedback.textContent='Preview could not play. Download the checker MP4 below to play locally.'});
 });
 keyed.addEventListener('play',()=>{play.textContent='Pause';play.setAttribute('aria-label','Pause comparison');synchronize(true);playSource();cancelFollow();follow()});
 keyed.addEventListener('pause',()=>{source.pause();synchronize(true);play.textContent='Play';play.setAttribute('aria-label','Play comparison');cancelFollow();updateTime()});
 keyed.addEventListener('ended',()=>{pause();updateTime()});
 keyed.addEventListener('seeking',()=>synchronize(true));keyed.addEventListener('seeked',()=>synchronize(true));
 keyed.addEventListener('ratechange',()=>{source.playbackRate=keyed.playbackRate});
 keyed.addEventListener('waiting',()=>source.pause());
 keyed.addEventListener('playing',()=>{synchronize(true);playSource()});
 keyed.addEventListener('timeupdate',updateTime);
 keyed.addEventListener('loadedmetadata',()=>{seek.max=String(keyed.duration);seek.disabled=!Number.isFinite(keyed.duration);updateTime();synchronize(true)});
 source.addEventListener('loadedmetadata',()=>{synchronize(true);if(!keyed.paused)playSource()});
 seek.addEventListener('input',()=>{keyed.currentTime=Number(seek.value);synchronize(true);updateTime()});
 source.addEventListener('error',()=>{sourceMissing=true;source.pause();source.hidden=true;divider.hidden=true;left.hidden=true;wipe.disabled=true;feedback.textContent='Original footage is unavailable. You can still play or download the keyed preview.'});
 keyed.addEventListener('error',()=>{pause();feedback.textContent='Preview could not play. Download the checker MP4 below to play locally.'});
 keyed.src=`/api/results/${jobId}/${encodeURIComponent(file)}`;source.src=`/api/jobs/${jobId}/source`;
 function dispose(){disposed=true;cancelFollow();for(const video of [keyed,source]){video.pause();video.removeAttribute('src');video.load()}}
 return {element,keyed,source,file,dispose};
}
