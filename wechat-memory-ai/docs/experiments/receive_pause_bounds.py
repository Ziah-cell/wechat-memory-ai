"""Offline bounds for owned-fixture debug stops, not exact OS scheduling time.

Lower: delivered event until Continue begins; successful freeze until close
begins. Upper: preceding empty-wait start / continuation start until continued,
plus attach/detach/freeze API brackets. Merge overlapping intervals across roles.
Unknown/missing trace cannot become a pass. Target latency includes scheduling.
"""

MARGIN_NS=1000  # larger than two ticks of the tested Windows QPC clock

def merged(intervals):
    result=[]
    for a,b in sorted(intervals):
        if b<a:raise ValueError('reversed_interval')
        if b==a:continue
        if result and a<=result[-1][1]:result[-1][1]=max(b,result[-1][1])
        else:result.append([a,b])
    return result

def metrics(intervals):
    spans=merged(intervals)
    return (max((b-a for a,b in spans),default=0)/1e6,sum(b-a for a,b in spans)/1e6,spans)

def assess(trace,witness=None):
    lower=[];upper=[];safe={};waits={};pending={};continues={};freeze={};api={}
    sequences={};errors=[];attached=False;detached=False
    for x in sorted(trace,key=lambda x:x['ns']):
        role=x['role'];op=x['op'];t=x['ns'];tid=x.get('tid',x.get('thread'))
        if role!='controller':
            if x.get('seq')!=sequences.get(role,0)+1:errors.append('trace_sequence')
            sequences[role]=x.get('seq')
        if op=='role_start':safe[role]=t
        elif op=='attach_begin':safe[role]=t;api[(role,'attach')]=t;attached=True
        elif op=='wait_begin':waits[role]=t
        elif op=='wait_end':
            if x['has_event'] and x['event_code']!=5:
                # A replay after DBG_REPLY_LATER starts a new known-stop span.
                if tid in pending:errors.append('event_without_continue')
                pending[tid]=(t,safe.get(role,t))
            elif not x['has_event'] and not pending:
                safe[role]=max(safe.get(role,0),waits.get(role,t))
            elif x.get('event_code')==5:detached=True
        elif op=='continue_begin':
            if tid in pending:
                start,bound=pending.pop(tid)
                if t-start>2*MARGIN_NS:lower.append([start+MARGIN_NS,t-MARGIN_NS])
                continues[role]=(bound,t)
        elif op=='continue_end':
            item=continues.pop(role,None)
            if item:
                bound,begin=item
                if x['success']:
                    upper.append([bound-MARGIN_NS,t+MARGIN_NS])
                    if x['status']!=0x40010001:safe[role]=begin
                else:errors.append('continue_failed')
        elif op=='freeze_begin':freeze[role]={'begin':t}
        elif op=='freeze_active':freeze[role]['active']=t
        elif op=='thaw_begin':
            if role in freeze:
                freeze[role]['end']=t
                start=freeze[role].get('active')
                if start is not None and t-start>2*MARGIN_NS:lower.append([start+MARGIN_NS,t-MARGIN_NS])
        elif op=='thaw_end':
            if role in freeze:upper.append([freeze.pop(role)['begin']-MARGIN_NS,t+MARGIN_NS])
        elif op=='kill_begin':
            f=freeze.get(x['victim'])
            if f and 'active' in f and t-f['active']>2*MARGIN_NS:lower.append([f['active']+MARGIN_NS,t-MARGIN_NS])
        elif op=='kill_end':
            f=freeze.pop(x['victim'],None)
            if f:upper.append([f['begin']-MARGIN_NS,t+MARGIN_NS])
        elif op=='detach_begin':api[(role,'detach')]=t
        elif op in ('attach_end','detach_end'):
            kind=op.split('_')[0];begin=api.pop((role,kind),None)
            if begin is None:errors.append('api_begin_missing')
            else:upper.append([begin-MARGIN_NS,t+MARGIN_NS])
            if not x['success']:errors.append(kind+'_failed')
            elif kind=='detach':detached=True
    lmax,ltotal,lspans=metrics(lower);umax,utotal,uspans=metrics(upper)
    unclosed=len(pending)+len(continues)+len(freeze)+len(api)
    covered=all(any(ua<=la and lb<=ub for ua,ub in uspans) for la,lb in lspans)
    if not covered:errors.append('lower_not_covered')
    ticks=(witness or {}).get('ticks',[])
    contradictions=sum(any(a<t<b for a,b in lspans) for t in ticks)
    if contradictions:errors.append('target_ran_in_known_stop')
    if (witness or {}).get('overflow'):errors.append('witness_overflow')
    if errors or unclosed or not attached or not detached:policy='cannot_certify'
    elif lmax>100 or ltotal>1000:policy='exceeded'
    elif umax<=100 and utotal<=1000:policy='within_conservative_bounds'
    else:policy='cannot_certify'
    return {'lower_max_ms':round(lmax,6),'lower_total_ms':round(ltotal,6),
            'upper_max_ms':round(umax,6),'upper_total_ms':round(utotal,6),
            'lower_intervals':len(lspans),'upper_intervals':len(uspans),
            'unclosed_intervals':unclosed,'witness_ticks_inside_known_stop':contradictions,
            'errors':sorted(set(errors)),'policy':policy,
            'exact_kernel_pause_measured':False,'live_runtime_gate':False}
