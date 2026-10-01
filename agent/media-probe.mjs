// RTSP r_frame_rate can be the codec's field clock (for example 60 for 30
// progressive frames). Count unique presentation timestamps, without decoding.
export function measuredVideoProbe(result){
  const stream=result?.streams?.find(s=>s.codec_type==='video');
  if(!Number.isSafeInteger(stream?.width)||!Number.isSafeInteger(stream?.height)||stream.width<16||stream.height<16||!Array.isArray(result.packets))return null;
  const points=new Set();let lastDts=-Infinity,lastPts=null;
  for(const p of result.packets){
    // Live RTSP opens with codec headers and an initial decoder warm-up prefix
    // without DTS. Start the measurement only when both clocks are available;
    // missing/invalid clocks after measurement starts remain a hard failure.
    if(typeof p.pts_time!=='string'||typeof p.dts_time!=='string'||!p.pts_time.trim()||!p.dts_time.trim()){
      if(lastDts===-Infinity)continue;
      return null;
    }
    const pts=Number(p.pts_time),dts=Number(p.dts_time);
    if(!Number.isFinite(pts)||!Number.isFinite(dts)||dts<lastDts-1e-6)return null;
    if(dts===lastDts&&pts!==lastPts)return null;
    points.add(pts);lastDts=dts;lastPts=pts;
  }
  const sorted=[...points].sort((a,b)=>a-b),duration=sorted.at(-1)-sorted[0];
  if(sorted.length<4||!Number.isFinite(duration)||duration<.5)return null;
  const fps=(sorted.length-1)/duration;
  if(!Number.isFinite(fps)||fps<=0||fps>1000)return null;
  return {width:stream.width,height:stream.height,fps,frames:sorted.length,duration};
}
