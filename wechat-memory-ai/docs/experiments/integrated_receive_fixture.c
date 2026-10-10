/* Integrates frozen own-process components at compile time. No external PID.
 * Their standalone entry points are renamed and never called by this main. */
#define main publisher_component_main
#define original publisher_component_original
#include "resident_publisher_fixture.c"
#undef original
#undef main
#define main trampoline_component_main
#define original generated_original
#include "executed_trampoline_fixture.c"
#undef original
#undef main

static Publisher *integrated_owner;
static int skip_publish;
static RUNTIME_FUNCTION integrated_table[3];

/* Payload is this Hook's own bounded local copy of four known integer arguments.
 * No output, allocation, wait, database work or consumer query inside this hook. */
__declspec(noinline) static uint64_t integrated_hook(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {
    InterlockedIncrement(&hook_entries);
    uint64_t value[4]={a,b,c,d};
    if(!skip_publish) publish(integrated_owner,value,(unsigned)e);
    uint64_t result=int_trampoline(a,b,c,d,e,f);
    InterlockedIncrement(&hook_returns);
    atomic_fetch_add(&integrated_owner->original_calls,1); /* Successful forwarded return. */
    return result;
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
    printf("{\"event\":\"status\",\"state\":%u,\"published\":%llu,\"original\":%llu,\"errors\":%llu,\"hook_entries\":%ld,\"hook_returns\":%ld}\n",
           atomic_load(&p->s->state),(unsigned long long)atomic_load(&p->s->published),
           (unsigned long long)atomic_load(&p->original_calls),(unsigned long long)atomic_load(&p->errors),
           InterlockedCompareExchange(&hook_entries,0,0),InterlockedCompareExchange(&hook_returns,0,0));
}
static DWORD WINAPI integrated_worker(void *arg) {
    Worker *w=arg;
    if(WaitForSingleObject(w->start,INFINITE)!=WAIT_OBJECT_0) return 21;
    for(unsigned i=0;i<w->count;i++){integrated_call(w->p,PAYLOAD);if(w->delay) Sleep(w->delay);}
    return 0;
}
static int integrated_target(const char *name,const char *epoch) {
    Publisher p={0};integrated_owner=&p;
    p.mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,4096,name);
    if(!p.mapping) return error("create_mapping",20);
    if(GetLastError()==ERROR_ALREADY_EXISTS){CloseHandle(p.mapping);return error("mapping_exists",10);}
    p.s=MapViewOfFile(p.mapping,FILE_MAP_WRITE,0,0,sizeof(Shared));
    if(!p.s) return error("map_target",20);
    memset(p.s,0,sizeof(Shared));p.s->version=1;p.s->bytes=sizeof(Shared);p.s->pid=GetCurrentProcessId();
    p.s->created=creation(GetCurrentProcess());if(!p.s->created) return error("creation",20);
    memcpy(p.s->epoch,epoch,33);atomic_init(&p.s->published,0);atomic_init(&p.s->state,ACTIVE);
    atomic_init(&p.gate,0);atomic_init(&p.inputs,0);atomic_init(&p.original_calls,0);atomic_init(&p.errors,0);
    p.s->magic=MAGIC;
    if(!integrated_setup()) return error("setup",22);
    printf("{\"event\":\"ready\",\"pid\":%lu,\"capacity\":8,\"registered_entries\":3,\"all_lookups_match\":true,\"lock_free\":%s}\n",
           GetCurrentProcessId(),atomic_is_lock_free(&p.s->published)&&atomic_is_lock_free(&p.s->state)?"true":"false");
    char line[128];HANDLE threads[8]={0},start=NULL;Worker workers[8];unsigned nthreads=0;
    while(fgets(line,sizeof(line),stdin)) {
        unsigned n=0,len=0,delay=0;
        if(sscanf(line,"call %u %u",&n,&len)==2&&n<=1000000&&!nthreads) {
            for(unsigned i=0;i<n;i++) integrated_call(&p,len);
            integrated_status(&p);
        } else if(sscanf(line,"workers %u %u %u",&n,&len,&delay)==3&&n>=1&&n<=8&&len<=1000000&&delay<=10&&!nthreads) {
            start=CreateEventW(NULL,TRUE,FALSE,NULL);if(!start) return error("start_event",20);
            for(unsigned i=0;i<n;i++) {
                workers[i]=(Worker){&p,start,len,delay};threads[i]=CreateThread(NULL,0,integrated_worker,&workers[i],0,NULL);
                if(!threads[i]) return error("worker_thread",20);
                nthreads++;
            }
            if(!SetEvent(start)) return error("start_workers",20);
            puts("{\"event\":\"started\"}");
        } else if(!strcmp(line,"join\n")) {
            if(!join_workers(threads,&nthreads,&start)) return error("join",20);
            integrated_status(&p);
        } else if(!strcmp(line,"status\n")) integrated_status(&p);
        else if(!strcmp(line,"stop\n")){fault(&p,STOPPED);integrated_status(&p);}
        else if(!strcmp(line,"busy\n")&&!nthreads){atomic_store(&p.gate,1);integrated_call(&p,PAYLOAD);atomic_store(&p.gate,0);integrated_status(&p);}
        else if(!strcmp(line,"quit\n")) break;
        else puts("{\"event\":\"error\",\"reason\":\"command\"}");
    }
    atomic_store(&p.s->state,EXITING);
    if(!join_workers(threads,&nthreads,&start)) return error("exit_join",20);
    int restored=integrated_patch(0)&&!memcmp(page+0x100,prefix,5);
    int deleted=RtlDeleteFunctionTable(integrated_table)!=0,absent=1;
    for(int i=0;i<3;i++){DWORD64 base=0;if(RtlLookupFunctionEntry((DWORD64)(uintptr_t)(page+integrated_table[i].BeginAddress),&base,NULL)) absent=0;}
    int freed=deleted&&VirtualFree(page,0,MEM_RELEASE)!=0;
    int mapping_closed=UnmapViewOfFile(p.s)&&CloseHandle(p.mapping);
    printf("{\"event\":\"bye\",\"prefix_restored\":%s,\"table_deleted\":%s,\"lookups_absent\":%s,\"freed\":%s,\"mapping_closed\":%s}\n",
           restored?"true":"false",deleted?"true":"false",absent?"true":"false",freed?"true":"false",mapping_closed?"true":"false");
    return restored&&deleted&&absent&&freed&&mapping_closed?0:23;
}
int main(int argc,char **argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);setvbuf(stdout,NULL,_IONBF,0);
    if((argc!=4&&argc!=5)||strncmp(argv[2],"Local\\VXOwnPublisher-",21)||!valid_epoch(argv[3])) return error("arguments",12);
    if(argc==5){if(strcmp(argv[1],"target")||strcmp(argv[4],"skip_publish")) return error("mode",12);skip_publish=1;}
    if(!strcmp(argv[1],"target")) return integrated_target(argv[2],argv[3]);
    if(!strcmp(argv[1],"consumer")) return consumer(argv[2],argv[3]);
    return error("role",12);
}
