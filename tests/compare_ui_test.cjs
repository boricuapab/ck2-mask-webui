const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this.attributes={};this.style={setProperty:(key,value)=>this.style[key]=value};this.currentTime=0;this.duration=4;this.readyState=4;this.paused=true;this.playbackRate=1;this.playCalls=0;this.callbacks=new Set()}
 append(...children){this.children.push(...children)}
 setAttribute(key,value){this.attributes[key]=value}
 removeAttribute(key){delete this.attributes[key];if(key==='src')this.src=''}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn)}
 emit(name){for(const fn of this.events[name]||[])fn()}
 play(){this.playCalls++;if(this.paused){this.paused=false;this.emit('play');this.emit('playing')}return Promise.resolve()}
 pause(){if(!this.paused){this.paused=true;this.emit('pause')}}
 load(){this.loaded=true}
 requestVideoFrameCallback(fn){this.callbacks.add(fn);return fn}
 cancelVideoFrameCallback(fn){this.callbacks.delete(fn)}
}
const context={document:{createElement:tag=>new Element(tag)},requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/compare.js'),'utf8'),context);
let saved;
const player=context.createWipeComparison({jobId:'job',file:'checker.mp4',metadata:{width:1280,height:720},onPosition:value=>saved=value});
const stage=player.element.children[0],controls=player.element.children[1];
const wipe=stage.children.find(node=>node.className==='wipe-slider'),play=controls.children[0],seek=controls.children[1];
assert.equal(stage.style.aspectRatio,'1280 / 720');
assert.equal(player.source.src,'/api/jobs/job/source');
assert.equal(stage.style['--wipe'],'50%');
wipe.value='75';wipe.emit('input');assert.equal(stage.style['--wipe'],'75%');assert.equal(saved,75);
player.keyed.duration=2;player.keyed.emit('loadedmetadata');assert.equal(seek.max,'2');
seek.value='1.25';seek.emit('input');assert.equal(player.keyed.currentTime,1.25);assert.equal(player.source.currentTime,1.25);
play.emit('click');assert.equal(player.keyed.paused,false);assert.equal(player.source.paused,false);assert.equal(play.textContent,'Pause');
player.keyed.playbackRate=1.5;player.keyed.emit('ratechange');assert.equal(player.source.playbackRate,1.5);
play.emit('click');assert.equal(player.keyed.paused,true);assert.equal(player.source.paused,true);
player.keyed.ended=true;play.emit('click');assert.equal(player.keyed.currentTime,0);assert.equal(player.source.currentTime,0);
player.keyed.emit('waiting');assert.equal(player.source.paused,true);
player.keyed.emit('playing');assert.equal(player.source.paused,false);
player.source.emit('error');assert.equal(wipe.disabled,true);assert.equal(player.source.hidden,true);
const calls=player.source.playCalls;play.emit('click');play.emit('click');assert.equal(player.source.playCalls,calls);
player.dispose();assert.equal(player.keyed.src,'');assert.equal(player.source.src,'');assert.equal(player.keyed.callbacks.size,0);
assert.equal(player.keyed.paused,true);assert.equal(player.source.paused,true);
console.log('Wipe position, synchronized seek/play/pause/rate, buffering, missing-source fallback, and disposal passed.');
