import React, { useEffect, useState } from 'react';
import { Execution } from '../types';

interface Props {execution:Execution|null;onApprove:(execution:Execution)=>Promise<void>;onRetry:(execution:Execution)=>Promise<void>}
export const DiffViewer:React.FC<Props> = ({execution,onApprove,onRetry}) => {
  const [active,setActive] = useState(0);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [showSource,setShowSource] = useState(false);
  useEffect(()=>{setActive(0);setError('');},[execution?.id]);
  if(!execution) return <div className="mono-panel p-10 rounded-lg text-sm text-zinc-400">Select an execution to inspect its proposal.</div>;
  const files=execution.generated_files || [];
  const file=files[active] || files[0];
  const validation=execution.validation_results;
  const checks=Object.values(validation?.checks || {});
  const action=async (callback:(run:Execution)=>Promise<void>)=>{
    setBusy(true);setError('');try{await callback(execution);}catch(err){setError((err as Error).message);}finally{setBusy(false);}
  };
  return <div className="mono-panel rounded-lg overflow-hidden text-xs">
    <div className="p-4 bg-zinc-950 border-b border-zinc-800 space-y-2">
      <p className="font-semibold">{execution.automation_title} · {execution.status}</p>
      <p className="text-zinc-400">{validation?.is_valid===true ? `${checks.filter(Boolean).length}/${checks.length} static checks passed`
        : validation?.is_valid===false ? 'Validation rejected this proposal' : 'Validation has not completed'}</p>
      <p className="text-zinc-500">{validation?.sandbox?.passed?`${validation.sandbox.tests_run} Python tests passed in an isolated container.`:'Generated code and tests have not been executed.'}</p>
      {validation?.errors?.map((message,index)=><p key={index} className="text-red-300">{message}</p>)}
      {execution.error_message && <p className="text-red-300">{execution.error_message}</p>}
      {execution.published_change?.pull_request_url && <a href={execution.published_change.pull_request_url} target="_blank" rel="noreferrer" className="underline">Open published pull request</a>}
      <div className="flex gap-2">
        {execution.status==='AWAITING_APPROVAL' && <button disabled={busy || !execution.proposal_hash} onClick={()=>action(onApprove)} className="bg-white text-black p-2 rounded">Approve reviewed proposal</button>}
        {execution.status==='FAILED' && execution.attempt_number<8 && <button disabled={busy} onClick={()=>action(onRetry)} className="border border-zinc-700 p-2 rounded">Retry original execution</button>}
      </div>
      {error && <p role="alert" className="text-red-300">{error}</p>}
    </div>
    {file ? <>
      <div className="flex gap-2 p-3 overflow-x-auto">{files.map((item,index)=><button key={item.id} onClick={()=>setActive(index)} className={`p-2 rounded whitespace-nowrap ${active===index?'bg-zinc-800':'text-zinc-400'}`}>{item.file_path}</button>)}</div>
      <div className="px-4 pb-4"><button className="mb-2 text-zinc-400 underline" onClick={()=>setShowSource(!showSource)}>{showSource?'Show changes':'Show complete proposed file'}</button>
        <pre className="overflow-x-auto p-4 bg-black border border-zinc-800 rounded font-mono whitespace-pre"><code>{showSource?file.new_content:file.diff_patch || 'No diff available for this legacy execution.'}</code></pre>
      </div>
    </> : <p className="p-4 text-zinc-400">No validated proposal files available.</p>}
  </div>;
};
