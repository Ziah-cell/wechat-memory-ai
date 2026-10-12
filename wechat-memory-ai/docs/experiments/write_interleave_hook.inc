#include "shared_write_protocol.h"
#define main trampoline_component_main
#define original generated_original
#include "executed_trampoline_fixture.c"
#undef original
#undef main

static Publisher *integrated_owner;
static int broad_filter;
static RUNTIME_FUNCTION integrated_table[3];
static BYTE *guard_memory;
static _Thread_local unsigned capture_depth;
static volatile LONG capture_faults, nested_skips, original_exceptions;
static LONG copy_fault_offset=-1;
enum { NORMAL, CAPTURE_BEFORE, CAPTURE_PARTIAL, CAPTURE_AFTER_RETURN, CAPTURE_AFTER_PUBLISH,
       ORIGINAL_FAULT, REENTRANT, REENTRANT_ORIGINAL_FAULT };
static _Thread_local int scenario;
static int leak_gate, global_depth;
static _Atomic unsigned shared_depth;
static _Thread_local int tls_role;
static HANDLE tls_held,tls_release;
static volatile LONG tls_workers,tls_depth_zero;
static DWORD tls_ids[2];
static LONG fault_stage;
enum { GATE_ENTER=8, GATE_PARTIAL, GATE_PRECOMMIT, GATE_POSTCOMMIT };
static unsigned depth_get(void){return global_depth?atomic_load(&shared_depth):capture_depth;}
static void depth_set(unsigned x){if(global_depth) atomic_store(&shared_depth,x);else capture_depth=x;}

/* All race events are test-only; they deliberately park a worker. */
static int late_stop, skip_recheck, race_prepared_mode, race_open;
static _Thread_local int race_role;
static HANDLE race_first_ready,race_prepared,race_released,race_done,race_resume;
static HANDLE race_threads[2];
static uint32_t window_state,window_gate;
static uint64_t window_published;
static LONG second_candidate,second_publish_entered,second_gate_acquired;
static void tls_abort(void);
static void race_wait(HANDLE h){if(WaitForSingleObject(h,5000)!=WAIT_OBJECT_0) tls_abort();}
static void race_signal(HANDLE h){if(!SetEvent(h)) tls_abort();}

extern void capture_copy32(const void *source,void *dest);
extern char capture_copy_start, capture_copy_end;

static LONG capture_read_filter(EXCEPTION_POINTERS *ep) {
    EXCEPTION_RECORD *r=ep->ExceptionRecord;
    if(r->ExceptionCode!=EXCEPTION_ACCESS_VIOLATION) return EXCEPTION_CONTINUE_SEARCH;
    uintptr_t pc=(uintptr_t)r->ExceptionAddress;
    int own=pc>=(uintptr_t)&capture_copy_start && pc<(uintptr_t)&capture_copy_end &&
        r->NumberParameters>=2 && r->ExceptionInformation[0]==0 &&
        r->ExceptionInformation[1]>=(uintptr_t)(guard_memory+4096) &&
        r->ExceptionInformation[1]<(uintptr_t)(guard_memory+8192);
    if(!own&&!broad_filter) return EXCEPTION_CONTINUE_SEARCH;
    copy_fault_offset=own?(LONG)(pc-(uintptr_t)&capture_copy_start):-2;
    return EXCEPTION_EXECUTE_HANDLER;
}

extern void shared_write64(_Atomic uint64_t *dest,uint64_t value);
extern void foreign_write64(_Atomic uint64_t *dest,uint64_t value);
extern char shared_write_site,shared_write_site_end,foreign_write_site;
static _Thread_local _Atomic uint64_t *write_expected;
static _Thread_local int write_armed;
static int write_point=-1,write_input=1,write_kind,skip_write_guard,publish_early;
static volatile LONG write_seen,write_handled,outer_caught,work_returns,work_depth_clear,work_armed_clear;
static LONG seen_operation=-1,seen_site=-1,seen_offset=-1,seen_field=-1;
static DWORD seen_code,record_protection,control_protection;
static int protection_changed;
static _Thread_local int current_field;

/* Only test scheduling uses events. Slots/control retain the frozen v3 ABI. */
static _Thread_local int iw_role;
static int iw_open,iw_kind,iw_mode,iw_shared_arm;
static HANDLE iw_ready,iw_prepared,iw_second_go,iw_hit[3],iw_go[3],iw_threads[2];
static _Atomic uint64_t *iw_first_address;
typedef struct {DWORD tid,code;LONG seen,handled,op,site,offset,armed,match,depth,gate,returned,propagated,clear,writes,acquired;} IwDiag;
static IwDiag iw_diag[4];
static LONG iw_phase_armed[3],iw_phase_depth[3];
static void iw_pause(int phase){
    iw_phase_armed[phase]=write_armed;iw_phase_depth[phase]=(LONG)depth_get();
    race_signal(iw_hit[phase]);race_wait(iw_go[phase]);
}

static int site_kind(uintptr_t pc){return pc==(uintptr_t)&shared_write_site?0:pc==(uintptr_t)&foreign_write_site?1:2;}
static LONG capture_filter(EXCEPTION_POINTERS *ep){
    EXCEPTION_RECORD *r=ep->ExceptionRecord;
    if(r->ExceptionCode!=EXCEPTION_ACCESS_VIOLATION)return EXCEPTION_CONTINUE_SEARCH;
    uintptr_t pc=(uintptr_t)r->ExceptionAddress,lo=(uintptr_t)integrated_owner->s->records;
    uintptr_t hi=lo+sizeof integrated_owner->s->records,address=r->NumberParameters>=2?r->ExceptionInformation[1]:0;
    InterlockedIncrement(&write_seen);seen_code=r->ExceptionCode;seen_operation=r->NumberParameters>=2?(LONG)r->ExceptionInformation[0]:-1;
    seen_site=site_kind(pc);seen_offset=address>=lo&&address<hi?(LONG)(address-lo):-1;seen_field=current_field;
    int owned=pc==(uintptr_t)&shared_write_site&&r->NumberParameters>=2&&r->ExceptionInformation[0]==1&&
        (iw_shared_arm&&iw_role==3?1:write_armed)&&(iw_shared_arm&&iw_role==3?iw_first_address:write_expected)&&
        address==(uintptr_t)(iw_shared_arm&&iw_role==3?iw_first_address:write_expected)&&address>=lo&&address+8<=hi&&!(address&7)&&
        depth_get()==1&&atomic_load(&integrated_owner->gate)==1;

    if(iw_role){
        IwDiag *d=&iw_diag[iw_role];d->seen++;d->code=r->ExceptionCode;d->handled+=owned;d->op=seen_operation;d->site=seen_site;d->offset=seen_offset;
        d->armed=write_armed;d->match=address==(uintptr_t)write_expected;d->depth=(LONG)depth_get();d->gate=(LONG)atomic_load(&integrated_owner->gate);
        if(iw_role==1){iw_first_address=write_expected;iw_pause(0);}
    }
    if(broad_filter||(!skip_write_guard&&owned)){InterlockedIncrement(&write_handled);return EXCEPTION_EXECUTE_HANDLER;}
    return capture_read_filter(ep);
}
/* Permission changes are fault-injection ONLY. The admitted store itself is
   the same instruction in healthy and faulting calls. No recovery remap. */
static void write_slot(Publisher *p,Record *r,_Atomic uint64_t *dest,uint64_t value,int field,uint64_t id){
    if(iw_role)iw_diag[iw_role].writes++;
    current_field=field;write_expected=dest;write_armed=1;
    int inject=(int)id==write_input&&field==write_point&&write_kind!=3;
    if(inject){
        if(write_kind==2)write_expected=(_Atomic uint64_t *)(guard_memory+4096);
        else {DWORD prior;if(!VirtualProtect(p->s->records,4096,PAGE_READONLY,&prior))tls_abort();protection_changed=1;}
    }
    (void)r;
    if(inject&&write_kind==1)foreign_write64(write_expected,value);
    else shared_write64(write_expected,value);
    write_armed=0;write_expected=NULL;
}
/* Only the outer TEST observer catches rejected fixture faults. It does not
   turn the interrupted invocation into a successful return. */
static LONG boundary_observer(EXCEPTION_POINTERS *ep){
    EXCEPTION_RECORD *r=ep->ExceptionRecord;uintptr_t pc=(uintptr_t)r->ExceptionAddress;
    int site=pc==(uintptr_t)&shared_write_site||pc==(uintptr_t)&foreign_write_site;
    int original=pc>=(uintptr_t)(page+0x100)&&pc<(uintptr_t)(page+0x100+integer_size);
    return r->ExceptionCode==EXCEPTION_ACCESS_VIOLATION&&((site&&write_armed&&r->NumberParameters>=2&&r->ExceptionInformation[1]==(uintptr_t)write_expected)||original)?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH;
}
static void write_status(Publisher *p){
    MEMORY_BASIC_INFORMATION info;
    if(VirtualQuery(p->s,&info,sizeof info))control_protection=info.Protect;
    if(VirtualQuery(p->s->records,&info,sizeof info))record_protection=info.Protect;
    printf("{\"event\":\"write_status\",\"seen\":%ld,\"handled\":%ld,\"outer_caught\":%ld,\"work_returns\":%ld,\"depth_clear\":%ld,\"armed_clear\":%ld,\"operation\":%ld,\"site\":%ld,\"address_offset\":%ld,\"field\":%ld,\"code\":%lu,\"control_protection\":%lu,\"record_protection\":%lu,\"protection_changed\":%s,\"stamp\":%llu,\"seq\":%llu,\"words\":[%llu,%llu,%llu,%llu]}\n",
        write_seen,write_handled,outer_caught,work_returns,work_depth_clear,work_armed_clear,seen_operation,seen_site,seen_offset,seen_field,seen_code,control_protection,record_protection,protection_changed?"true":"false",
        (unsigned long long)atomic_load(&p->s->records[0].stamp),(unsigned long long)atomic_load(&p->s->records[0].seq),
        (unsigned long long)atomic_load(&p->s->records[0].word[0]),(unsigned long long)atomic_load(&p->s->records[0].word[1]),
        (unsigned long long)atomic_load(&p->s->records[0].word[2]),(unsigned long long)atomic_load(&p->s->records[0].word[3]));
    const unsigned char *code=(const unsigned char *)&shared_write_site;
    printf("{\"event\":\"write_site\",\"span\":%llu,\"bytes\":[%u,%u,%u]}\n",
        (unsigned long long)((uintptr_t)&shared_write_site_end-(uintptr_t)&shared_write_site),code[0],code[1],code[2]);
}

/* Test-only protected read interrupts an acquired-gate interval. This is
 * NOT an AV at the shared record/store instruction or a generic fault guard. */
static void gate_probe(int point) {
    if(scenario==point){uint64_t scratch[4];fault_stage=point-GATE_ENTER+1;capture_copy32(guard_memory+4096,scratch);}
}
static void guarded_publish(Publisher *p,const void *ptr,unsigned length) {
    if(race_role==2) second_publish_entered=1;
    if(atomic_load(&p->s->state)!=ACTIVE) return;
    if(length!=PAYLOAD){fault(p,INVALID);return;}
    if(iw_role==2&&iw_kind==2){race_signal(iw_prepared);race_wait(iw_second_go);}
    if(race_role==2&&race_prepared_mode==2){race_signal(race_prepared);race_wait(race_released);}
    uint32_t empty=0;
    if(!atomic_compare_exchange_strong(&p->gate,&empty,1)){fault(p,BUSY);return;}
    if(race_role==2) second_gate_acquired=1;
    if(iw_role)iw_diag[iw_role].acquired=1;
    volatile int completed=0;
    __try {
        gate_probe(GATE_ENTER);
        if(atomic_load(&p->s->state)==ACTIVE||skip_recheck) {
            uint64_t n=atomic_load_explicit(&p->s->published,memory_order_relaxed);
            if(n>=MAX_SEQUENCE) fault(p,INVALID);
            else if(n-atomic_load(&p->s->acked)>=CAPACITY&&!overwrite) fault(p,FULL);
            else {
                Record *r=&p->s->records[n%CAPACITY];
                uint64_t words[4];memcpy(words,ptr,sizeof words);
                write_slot(p,r,&r->stamp,(n+1)*2-1,0,words[0]);write_slot(p,r,&r->seq,n+1,1,words[0]);
                for(unsigned i=0;i<2;i++)write_slot(p,r,&r->word[i],words[i],2+(int)i,words[0]);gate_probe(GATE_PARTIAL);
                for(unsigned i=2;i<4;i++)write_slot(p,r,&r->word[i],words[i],2+(int)i,words[0]);gate_probe(GATE_PRECOMMIT);
                if(publish_early)atomic_store(&p->s->published,n+1); /* Deliberately wrong ordering. */
                write_slot(p,r,&r->stamp,(n+1)*2,6,words[0]);
                atomic_store_explicit(&p->s->published,n+1,memory_order_release);
                gate_probe(GATE_POSTCOMMIT);
            }
        }
        completed=1;
    } __finally {
        /* End admission while this writer still owns the gate. The outer
         * filter still decides whether an exception may be handled at all. */
        if(!completed&&!late_stop) fault(p,INVALID);
        if(iw_role==1)iw_pause(1);
        if(!leak_gate) atomic_store(&p->gate,0);
        write_armed=0;write_expected=NULL;
        if(iw_role==1)iw_pause(2);
        if(race_role==1) {
            window_state=atomic_load(&p->s->state);window_gate=atomic_load(&p->gate);
            window_published=atomic_load(&p->s->published);
            race_signal(race_released);race_wait(race_resume);
        }
    }
}
static uint64_t forward_original(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {
    uint64_t result=int_trampoline(a,b,c,d,e,f);
    InterlockedIncrement(&hook_returns);atomic_fetch_add(&integrated_owner->original_calls,1);
    return result;
}
static LONG outer_original_filter(EXCEPTION_POINTERS *ep) {
    uintptr_t pc=(uintptr_t)ep->ExceptionRecord->ExceptionAddress;
    return ep->ExceptionRecord->ExceptionCode==EXCEPTION_ACCESS_VIOLATION &&
        pc>=(uintptr_t)(page+0x100) && pc<(uintptr_t)(page+0x100+integer_size)
        ?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH;
}

/* Only the declared copy/read pair or armed shared-write site/address pair
 * can be handled. Original invocation remains outside capture __except. */
__declspec(noinline) static uint64_t integrated_hook(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {
    InterlockedIncrement(&hook_entries);
    if(depth_get()) {InterlockedIncrement(&nested_skips);return forward_original(a,b,c,d,e,f);}
    depth_set(1);
    /* Deterministic test barrier before candidate copy, outside gate ownership. */
    __try {
        if(tls_role==1) {
            if(!SetEvent(tls_held)||WaitForSingleObject(tls_release,5000)!=WAIT_OBJECT_0)
                atomic_fetch_add(&integrated_owner->errors,1);
        }
        uint64_t value[4]={0},source[4]={a,b,c,d};int ready=0;
        if(atomic_load(&integrated_owner->s->state)==ACTIVE) {
            __try {
                const void *from=source;
                if(scenario==CAPTURE_BEFORE) from=guard_memory+4096;
                if(scenario==CAPTURE_PARTIAL){memcpy(guard_memory+4080,source,16);from=guard_memory+4080;}
                capture_copy32(from,value);
                if(scenario==REENTRANT||scenario==REENTRANT_ORIGINAL_FAULT) {
                    uint64_t child=scenario==REENTRANT?900000:0;
                    uint64_t got=int_entry(child,2,3,4,32,0x55);
                    if(got!=expected(child,2,3,4,32,0x55)) atomic_fetch_add(&integrated_owner->errors,1);
                }
                ready=1;
            } __except(capture_filter(GetExceptionInformation())) {
                InterlockedIncrement(&capture_faults);fault(integrated_owner,INVALID);
            }
        }
        uint64_t result=forward_original(a,b,c,d,e,f);
        if(iw_role==1){race_signal(iw_ready);race_wait(iw_prepared);}
        if(iw_role==2&&iw_kind==1){race_signal(iw_prepared);race_wait(iw_second_go);}
        if(race_role==1) {
            race_signal(race_first_ready);
            if(race_prepared_mode) race_wait(race_prepared);
        }
        if(ready) {
            if(race_role==2) {
                second_candidate=1;
                if(race_prepared_mode==1){race_signal(race_prepared);race_wait(race_released);}
            }
            __try {
                uint64_t scratch[4];
                if(scenario==CAPTURE_AFTER_RETURN) capture_copy32(guard_memory+4096,scratch);
                guarded_publish(integrated_owner,value,(unsigned)e);
                if(scenario==CAPTURE_AFTER_PUBLISH) capture_copy32(guard_memory+4096,scratch);
            } __except(capture_filter(GetExceptionInformation())) {
                InterlockedIncrement(&capture_faults);fault(integrated_owner,INVALID);
            }
        }
        return result;
    } __finally {depth_set(0);}
}
static int integrated_patch(int install) {
    DWORD prior;
    if(!VirtualProtect(page,4096,PAGE_READWRITE,&prior)) return 0;
    if(install) {int32_t delta=0x300-0x100-5;page[0x100]=0xe9;memcpy(page+0x101,&delta,4);}
    else memcpy(page+0x100,prefix,5);
    DWORD ignored;
    return VirtualProtect(page,4096,PAGE_EXECUTE_READ,&ignored)&&FlushInstructionCache(GetCurrentProcess(),page,4096);
}
static int integrated_setup(void) {
    page=VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if(!page) return 0;
    integer_size=generated_original(page+0x100,0);
    memcpy(page+0x200,prefix,5);jump_absolute(page+0x205,(uintptr_t)(page+0x105));
    jump_absolute(page+0x300,(uintptr_t)integrated_hook);
    const BYTE original_info[]={1,9,5,0,9,2,5,0x70,4,0x60,3,0xe0,1,0x50,0,0};
    const BYTE trampoline_info[]={1,18,4,0,5,0x70,4,0x60,3,0xe0,1,0x50};
    const BYTE leaf_info[]={1,0,0,0};
    memcpy(page+0x800,original_info,sizeof original_info);memcpy(page+0x820,trampoline_info,sizeof trampoline_info);
    memcpy(page+0x840,leaf_info,sizeof leaf_info);
    function_entry(&integrated_table[0],0x100,integer_size,0x800);
    function_entry(&integrated_table[1],0x200,18,0x820);function_entry(&integrated_table[2],0x300,13,0x840);
    DWORD prior;
    if(!VirtualProtect(page,4096,PAGE_EXECUTE_READ,&prior)||!FlushInstructionCache(GetCurrentProcess(),page,4096)) return 0;
    if(!RtlAddFunctionTable(integrated_table,3,(DWORD64)(uintptr_t)page)) return 0;
    for(int i=0;i<3;i++) {
        DWORD64 base=0;
        if(RtlLookupFunctionEntry((DWORD64)(uintptr_t)(page+integrated_table[i].BeginAddress),&base,NULL)!=&integrated_table[i]||base!=(DWORD64)(uintptr_t)page) return 0;
    }
    int_entry=(IntFunction)(uintptr_t)(page+0x100);int_trampoline=(IntFunction)(uintptr_t)(page+0x200);
    return integrated_patch(1);
}
static void integrated_call(Publisher *p,unsigned length) {
    uint64_t id=atomic_fetch_add(&p->inputs,1)+1;
    uint64_t b=id^0xa5a5a5a5ULL,c=id+7,d=id*3,f=0x55;
    if(int_entry(id,b,c,d,length,f)!=expected(id,b,c,d,length,f)) atomic_fetch_add(&p->errors,1);
}
static void integrated_status(Publisher *p) {
    printf("{\"event\":\"status\",\"state\":%u,\"acked\":%llu,\"gap\":%llu,\"published\":%llu,\"original\":%llu,\"errors\":%llu,\"hook_entries\":%ld,\"hook_returns\":%ld,\"depth\":%u,\"capture_faults\":%ld,\"nested_skips\":%ld,\"original_exceptions\":%ld,\"copy_fault_offset\":%ld,\"gate\":%u,\"fault_stage\":%ld,\"slot_seq\":%llu,\"slot_words\":[%llu,%llu,%llu,%llu],\"tls_workers\":%ld,\"tls_depth_zero\":%ld,\"tls_distinct\":%s,\"window_state\":%u,\"window_gate\":%u,\"window_published\":%llu,\"second_candidate\":%ld,\"second_publish_entered\":%ld,\"second_gate_acquired\":%ld}\n",
           atomic_load(&p->s->state),(unsigned long long)atomic_load(&p->s->acked),
           (unsigned long long)(atomic_load(&p->original_calls)-atomic_load(&p->s->published)),(unsigned long long)atomic_load(&p->s->published),
           (unsigned long long)atomic_load(&p->original_calls),(unsigned long long)atomic_load(&p->errors),
           InterlockedCompareExchange(&hook_entries,0,0),InterlockedCompareExchange(&hook_returns,0,0),
           depth_get(),capture_faults,nested_skips,original_exceptions,copy_fault_offset,
           atomic_load(&p->gate),fault_stage,(unsigned long long)p->s->records[0].seq,
           (unsigned long long)p->s->records[0].word[0],(unsigned long long)p->s->records[0].word[1],
           (unsigned long long)p->s->records[0].word[2],(unsigned long long)p->s->records[0].word[3],
           tls_workers,tls_depth_zero,tls_ids[0]&&tls_ids[1]&&tls_ids[0]!=tls_ids[1]?"true":"false",
           window_state,window_gate,(unsigned long long)window_published,
           second_candidate,second_publish_entered,second_gate_acquired);
}
static void run_scenario(Publisher *p,const char *name) {
    const char *names[]={"normal","capture_before","capture_partial","capture_after_return","capture_after_publish","original_fault","reentrant","reentrant_original_fault","gate_enter","gate_partial","gate_precommit","gate_postcommit"};
    scenario=-1;for(int i=0;i<12;i++) if(!strcmp(name,names[i])) scenario=i;
    if(scenario<0){puts("{\"event\":\"error\",\"reason\":\"scenario\"}");return;}
    __try {
        if(scenario==ORIGINAL_FAULT) int_entry(0,2,3,4,32,0x55);
        else integrated_call(p,PAYLOAD);
    } __except(outer_original_filter(GetExceptionInformation())) {InterlockedIncrement(&original_exceptions);}
    integrated_status(p);
}
typedef struct {int role,raises;} TlsWork;
static void tls_abort(void) {
    /* A setup/join failure cannot return past live workers' stack arguments.
     * Process termination is a FAILED fixture run, never cooperative cleanup. */
    error("tls_setup_or_join",25);ExitProcess(25);
}
static DWORD WINAPI tls_worker(void *arg) {
    TlsWork *w=arg;tls_role=w->role;
    tls_ids[w->role-1]=GetCurrentThreadId();
    scenario=w->raises?REENTRANT_ORIGINAL_FAULT:REENTRANT;
    __try {integrated_call(integrated_owner,PAYLOAD);}
    __except(outer_original_filter(GetExceptionInformation())) {InterlockedIncrement(&original_exceptions);}
    if(depth_get()==0) InterlockedIncrement(&tls_depth_zero);
    InterlockedIncrement(&tls_workers);
    if(w->role==2&&!SetEvent(tls_release)) atomic_fetch_add(&integrated_owner->errors,1);
    return 0;
}
static int run_tls(const char *name) {
    if(strcmp(name,"tls_overlap")&&strcmp(name,"tls_exception")) return 0;
    /* Each invocation uses fresh target/process state; intentionally only once. */
    if(tls_workers) return 0;
    tls_held=CreateEventW(NULL,TRUE,FALSE,NULL);tls_release=CreateEventW(NULL,TRUE,FALSE,NULL);
    if(!tls_held||!tls_release) return 0;
    TlsWork w[2]={{1,!strcmp(name,"tls_exception")},{2,0}};HANDLE threads[2];
    threads[0]=CreateThread(NULL,0,tls_worker,&w[0],0,NULL);
    if(!threads[0]||WaitForSingleObject(tls_held,5000)!=WAIT_OBJECT_0) tls_abort();
    threads[1]=CreateThread(NULL,0,tls_worker,&w[1],0,NULL);
    if(!threads[1]||WaitForMultipleObjects(2,threads,TRUE,8000)!=WAIT_OBJECT_0) tls_abort();
    DWORD code0=99,code1=99;
    int good=GetExitCodeThread(threads[0],&code0)&&GetExitCodeThread(threads[1],&code1)&&code0==0&&code1==0;
    good=CloseHandle(threads[0])&&good;good=CloseHandle(threads[1])&&good;
    good=CloseHandle(tls_held)&&good;good=CloseHandle(tls_release)&&good;
    return good;
}
typedef struct {int role,point;} RaceWork;
static DWORD WINAPI race_worker(void *arg) {
    RaceWork *w=arg;race_role=w->role;scenario=w->point;
    tls_ids[w->role-1]=GetCurrentThreadId();
    if(w->role==2&&!race_prepared_mode) race_wait(race_released);
    integrated_call(integrated_owner,PAYLOAD);
    if(depth_get()==0) InterlockedIncrement(&tls_depth_zero);
    InterlockedIncrement(&tls_workers);
    if(w->role==2) race_signal(race_done);
    return 0;
}
static void run_race_start(const char *name) {
    if(race_open||tls_workers) tls_abort();
    const char *names[]={"gate_enter_fresh","gate_enter_prepared","gate_enter_prechecked",
                         "gate_partial_fresh","gate_partial_prepared","gate_partial_prechecked",
                         "gate_precommit_fresh","gate_precommit_prepared","gate_precommit_prechecked",
                         "gate_postcommit_fresh","gate_postcommit_prepared","gate_postcommit_prechecked"};
    int index=-1;for(int i=0;i<12;i++) if(!strcmp(name,names[i])) index=i;
    if(index<0) tls_abort();race_prepared_mode=index%3;
    HANDLE *events[]={&race_first_ready,&race_prepared,&race_released,&race_done,&race_resume};
    for(unsigned i=0;i<5;i++){*events[i]=CreateEventW(NULL,TRUE,FALSE,NULL);if(!*events[i]) tls_abort();}
    static RaceWork w[2];w[0]=(RaceWork){1,GATE_ENTER+index/3};w[1]=(RaceWork){2,NORMAL};
    race_open=1;race_threads[0]=CreateThread(NULL,0,race_worker,&w[0],0,NULL);
    if(!race_threads[0]) tls_abort();race_wait(race_first_ready);
    race_threads[1]=CreateThread(NULL,0,race_worker,&w[1],0,NULL);
    if(!race_threads[1]) tls_abort();race_wait(race_done);race_wait(race_threads[1]);
    DWORD code=99;if(!GetExitCodeThread(race_threads[1],&code)||code) tls_abort();
    /* Worker1 is parked after unlock, worker2 has exited. No slot writer runs. */
}
static void run_race_finish(void) {
    if(!race_open) return;
    race_signal(race_resume);race_wait(race_threads[0]);
    DWORD code=99;if(!GetExitCodeThread(race_threads[0],&code)||code) tls_abort();
    HANDLE all[]={race_first_ready,race_prepared,race_released,race_done,race_resume,race_threads[0],race_threads[1]};
    for(unsigned i=0;i<7;i++) if(!CloseHandle(all[i])) tls_abort();
    race_open=0;
}
static int integrated_target(const char *name,const char *epoch) {
    Publisher p={0};integrated_owner=&p;
    guard_memory=VirtualAlloc(NULL,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    DWORD guard_prior;
    if(!guard_memory||!VirtualProtect(guard_memory+4096,4096,PAGE_NOACCESS,&guard_prior)) return error("guard_setup",24);
    p.mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(Shared),name);
    if(!p.mapping) return error("create_mapping",20);
    if(GetLastError()==ERROR_ALREADY_EXISTS){CloseHandle(p.mapping);return error("mapping_exists",10);}
    p.s=MapViewOfFile(p.mapping,FILE_MAP_WRITE,0,0,sizeof(Shared));
    if(!p.s) return error("map_target",20);
    memset(p.s,0,sizeof(Shared));p.s->version=3;p.s->bytes=sizeof(Shared);p.s->pid=GetCurrentProcessId();
    p.s->created=creation(GetCurrentProcess());if(!p.s->created) return error("creation",20);
    memcpy(p.s->epoch,epoch,33);atomic_init(&p.s->acked,0);atomic_init(&p.s->published,0);atomic_init(&p.s->state,ACTIVE);
    atomic_init(&p.gate,0);atomic_init(&p.inputs,0);atomic_init(&p.original_calls,0);atomic_init(&p.errors,0);
    for(unsigned i=0;i<CAPACITY;i++){
        atomic_init(&p.s->records[i].stamp,0);atomic_init(&p.s->records[i].seq,0);
        for(unsigned j=0;j<4;j++)atomic_init(&p.s->records[i].word[j],0);
    }
    p.s->magic=MAGIC;
    if(!integrated_setup()) return error("setup",22);
    printf("{\"event\":\"ready\",\"pid\":%lu,\"capacity\":8,\"mapping_bytes\":4096,\"registered_entries\":3,\"all_lookups_match\":true,\"lock_free\":%s}\n",
           GetCurrentProcessId(),atomic_is_lock_free(&p.s->published)&&atomic_is_lock_free(&p.s->state)?"true":"false");
    /* During a race window only resume/quit are accepted; worker1 is parked. */
    char line[128];
    while(fgets(line,sizeof(line),stdin)) {
        unsigned n=0,len=0;
        char scenario_name[48],ack_epoch[33];unsigned long long ack_seq,ack_generation;
        if(!strcmp(line,"resume\n")){run_race_finish();integrated_status(&p);}
        else if(!strcmp(line,"quit\n")){run_race_finish();break;}
        else if(race_open) puts("{\"event\":\"error\",\"reason\":\"race_open\"}");
        else if(sscanf(line,"ack %32s %llu %llu",ack_epoch,&ack_seq,&ack_generation)==3) acknowledge(&p,ack_epoch,ack_seq,ack_generation);
        else if(sscanf(line,"race %47s",scenario_name)==1){run_race_start(scenario_name);integrated_status(&p);}
        else if(sscanf(line,"tls %47s",scenario_name)==1) {
            if(!run_tls(scenario_name)) return error("tls_test",25);
            integrated_status(&p);
        }
        else if(sscanf(line,"scenario %47s",scenario_name)==1) run_scenario(&p,scenario_name);
        else if(sscanf(line,"call %u %u",&n,&len)==2&&n<=1000000) {
            for(unsigned i=0;i<n;i++) integrated_call(&p,len);
            integrated_status(&p);
        } else if(!strcmp(line,"status\n")) integrated_status(&p);
        else if(!strcmp(line,"stop\n")){fault(&p,STOPPED);integrated_status(&p);}
        else puts("{\"event\":\"error\",\"reason\":\"command\"}");
    }
    run_race_finish();
    atomic_store(&p.s->state,EXITING);
    int restored=integrated_patch(0)&&!memcmp(page+0x100,prefix,5);
    int deleted=RtlDeleteFunctionTable(integrated_table)!=0,absent=1;
    for(int i=0;i<3;i++){DWORD64 base=0;if(RtlLookupFunctionEntry((DWORD64)(uintptr_t)(page+integrated_table[i].BeginAddress),&base,NULL)) absent=0;}
    int freed=deleted&&VirtualFree(page,0,MEM_RELEASE)!=0;
    int mapping_closed=UnmapViewOfFile(p.s)&&CloseHandle(p.mapping);
    int guard_freed=VirtualFree(guard_memory,0,MEM_RELEASE)!=0;
    printf("{\"event\":\"bye\",\"prefix_restored\":%s,\"table_deleted\":%s,\"lookups_absent\":%s,\"freed\":%s,\"mapping_closed\":%s,\"guard_freed\":%s}\n",
           restored?"true":"false",deleted?"true":"false",absent?"true":"false",freed?"true":"false",mapping_closed?"true":"false",guard_freed?"true":"false");
    return restored&&deleted&&absent&&freed&&mapping_closed&&guard_freed?0:23;
}
