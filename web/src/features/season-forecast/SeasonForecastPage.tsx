import { useState } from "react";
import { runSeasonForecast } from "./api";
import type { ForecastRequest, ForecastResponse } from "./types";

const initial: ForecastRequest = { model:"iid_bootstrap", simulations:10000, history_years:[], venue_conditioning:true, memory:2, state_metric:"fantavoto", state_edges:[6,6.5,7.5], laplace:1, quantiles:[.1,.5,.9], metrics:["scoredGoals","assists","fantavoto","voto"] };
export function SeasonForecastPage({apiBaseUrl,player,year}:{apiBaseUrl:string;player:string;year:number}) {
 const [cfg,setCfg]=useState(initial), [data,setData]=useState<ForecastResponse|null>(null), [error,setError]=useState("");
 const run=async()=>{setError(""); try{setData(await runSeasonForecast(apiBaseUrl,player,year,cfg));}catch(e){setError(e instanceof Error?e.message:String(e));}};
 return <section aria-labelledby="forecast-title">
  <h1 id="forecast-title">Season Forecast · {player}</h1>
  <div className="forecast-controls">
   <label>Modello <select value={cfg.model} onChange={e=>setCfg({...cfg,model:e.target.value as ForecastRequest["model"]})}><option value="iid_bootstrap">Monte Carlo base</option><option value="markov_memory">Markov con memoria</option></select></label>
   <label>Simulazioni <input type="number" min={100} max={200000} value={cfg.simulations} onChange={e=>setCfg({...cfg,simulations:Number(e.target.value)})}/></label>
   {cfg.model==="markov_memory"&&<label>Memoria <input type="number" min={1} max={5} value={cfg.memory} onChange={e=>setCfg({...cfg,memory:Number(e.target.value)})}/></label>}
   <label><input type="checkbox" checked={cfg.venue_conditioning} onChange={e=>setCfg({...cfg,venue_conditioning:e.target.checked})}/> Condiziona casa/trasferta</label>
   <button onClick={run}>Simula stagione</button>
  </div>
  {error&&<p role="alert">{error}</p>}
  {data&&<><p>{data.fit.training_rows} righe reali · {data.fit.future_fixtures} partite programmate · {data.model}</p>
   <div className="forecast-grid">{Object.entries(data.metrics).map(([name,m])=><article key={name}><h2>{name}</h2><strong>{m.final_mean?.toFixed(2)??"n/d"}</strong><p>P10 {m.quantiles.p10?.toFixed(2)??"n/d"} · P50 {m.quantiles.p50?.toFixed(2)??"n/d"} · P90 {m.quantiles.p90?.toFixed(2)??"n/d"}</p></article>)}</div>
   {data.fit.warnings.map(w=><p role="status" key={w}>{w}</p>)}<small>{data.disclaimer}</small></>}
 </section>;
}
