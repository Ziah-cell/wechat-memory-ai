/* Owned harness; the independent hook include omits only the old main. */
#include "autonomous_relay_hook.inc"

typedef struct {uint32_t magic,pid;uint64_t created,seq,generation;char epoch[33];} AckPacket;
typedef struct {uint64_t acked;uint32_t ok,reason;} AckReply;
static HANDLE pipe_server,pipe_event,service_stop,service_thread,work_thread,work_stop,bound_peer;
static HANDLE ack_held,ack_release;
static _Atomic uint32_t peer_pid;
static _Atomic uint64_t peer_created,acks_ok,acks_rejected;
static volatile LONG pause_ack;
static int skip_peer,skip_target_binding,skip_cursor,publisher_held;
static unsigned work_count,work_delay;

static void pipe_name(char *dest,const char *mapping){snprintf(dest,128,"\\\\.\\pipe\\VXOwnRelay-%s",mapping+21);}
static int service_io(int op,void *data,DWORD size,DWORD *count){
    if(WaitForSingleObject(service_stop,0)==WAIT_OBJECT_0)return 0;
    OVERLAPPED ov={0};ov.hEvent=pipe_event;ResetEvent(pipe_event);*count=0;
    BOOL ok=op==0?ConnectNamedPipe(pipe_server,&ov):op==1?ReadFile(pipe_server,data,size,count,&ov):WriteFile(pipe_server,data,size,count,&ov);
    if(ok)return 1;
    DWORD err=GetLastError();if(op==0&&err==ERROR_PIPE_CONNECTED)return 1;
    if(err!=ERROR_IO_PENDING)return 0;
    HANDLE events[]={service_stop,pipe_event};DWORD waited=WaitForMultipleObjects(2,events,FALSE,INFINITE);
    if(waited!=WAIT_OBJECT_0+1){
        CancelIoEx(pipe_server,&ov);
        /* Cancellation request does not end OVERLAPPED lifetime: reap it. */
        GetOverlappedResult(pipe_server,&ov,count,TRUE);return 0;
    }
    return GetOverlappedResult(pipe_server,&ov,count,FALSE)!=0;
}
static AckReply process_ack(Publisher *p,const AckPacket *a){
    AckReply reply={atomic_load(&p->s->acked),0,1};ULONG actual_pid=0;
    if(!GetNamedPipeClientProcessId(pipe_server,&actual_pid))return reply;
    HANDLE actual=OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,actual_pid);
    if(!actual)return reply;
    int same=actual_pid==atomic_load(&peer_pid)&&creation(actual)==atomic_load(&peer_created)&&WaitForSingleObject(actual,0)==WAIT_TIMEOUT;
    CloseHandle(actual);
    if(!same&&!skip_peer)return reply;
    if(a->magic!=MAGIC||(!skip_target_binding&&(a->pid!=p->s->pid||a->created!=p->s->created))||(!skip_epoch&&memcmp(a->epoch,p->s->epoch,33)))return reply;
    uint32_t empty=0;
    if(!atomic_compare_exchange_strong(&p->gate,&empty,1)){reply.reason=2;return reply;}
    if(InterlockedExchange(&pause_ack,0)){
        SetEvent(ack_held);
        if(WaitForSingleObject(ack_release,5000)!=WAIT_OBJECT_0){fault(p,INVALID);atomic_store(&p->gate,0);reply.reason=5;return reply;}
    }
    uint64_t acked=atomic_load(&p->s->acked),published=atomic_load(&p->s->published);
    int valid=a->seq>acked&&a->seq<=published&&a->seq<=MAX_SEQUENCE&&a->generation==(a->seq-1)/CAPACITY+1&&atomic_load(&p->s->records[(a->seq-1)%CAPACITY].stamp)==a->seq*2;
    if(valid)atomic_store(&p->s->acked,a->seq);
    reply.acked=atomic_load(&p->s->acked);reply.ok=valid;reply.reason=valid?0:a->seq<=acked?4:3;
    atomic_store(&p->gate,0);return reply;
}
static DWORD WINAPI ack_service(void *arg){
    Publisher *p=arg;
    while(WaitForSingleObject(service_stop,0)!=WAIT_OBJECT_0){
        DWORD bytes=0;if(!service_io(0,NULL,0,&bytes))continue;
        while(WaitForSingleObject(service_stop,0)!=WAIT_OBJECT_0){
            AckPacket a={0};if(!service_io(1,&a,sizeof a,&bytes)||bytes!=sizeof a)break;
            AckReply reply=process_ack(p,&a);
            atomic_fetch_add(reply.ok?&acks_ok:&acks_rejected,1);
            if(!service_io(2,&reply,sizeof reply,&bytes)||bytes!=sizeof reply)break;
        }
        DisconnectNamedPipe(pipe_server);
    }
    return 0;
}
static DWORD WINAPI automatic_work(void *arg){
    Publisher *p=arg;
    for(unsigned i=0;i<work_count;i++){
        if(WaitForSingleObject(work_stop,0)==WAIT_OBJECT_0)break;
        integrated_call(p,PAYLOAD);
        if(work_delay)Sleep(work_delay); /* Workload pacing outside Hook. */
    }
    return 0;
}
static int finish_work(void){
    if(!work_thread)return 1;
    DWORD code=99;int ok=WaitForSingleObject(work_thread,15000)==WAIT_OBJECT_0&&GetExitCodeThread(work_thread,&code)&&!code;
    if(!ok)return 0;
    CloseHandle(work_thread);work_thread=NULL;return 1;
}
static void bind_peer(uint32_t pid,uint64_t created){
    if(bound_peer&&WaitForSingleObject(bound_peer,0)==WAIT_TIMEOUT){puts("{\"ok\":false,\"reason\":\"live_peer\"}");return;}
    HANDLE h=OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
    if(!h||creation(h)!=created||WaitForSingleObject(h,0)!=WAIT_TIMEOUT){if(h)CloseHandle(h);puts("{\"ok\":false,\"reason\":\"peer_binding\"}");return;}
    atomic_store(&peer_pid,0);atomic_store(&peer_created,created);atomic_store(&peer_pid,pid);
    if(bound_peer)CloseHandle(bound_peer);bound_peer=h;puts("{\"ok\":true}");
}
static int autonomous_target(const char *name,const char *epoch){
    Publisher p={0};integrated_owner=&p;
    guard_memory=VirtualAlloc(NULL,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);DWORD prior;
    if(!guard_memory||!VirtualProtect(guard_memory+4096,4096,PAGE_NOACCESS,&prior))return error("guard",24);
    p.mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,4096,name);
    if(!p.mapping||GetLastError()==ERROR_ALREADY_EXISTS)return error("mapping",20);
    p.s=MapViewOfFile(p.mapping,FILE_MAP_WRITE,0,0,sizeof(Shared));if(!p.s)return error("map",20);
    memset(p.s,0,sizeof(Shared));p.s->version=2;p.s->bytes=sizeof(Shared);p.s->pid=GetCurrentProcessId();p.s->created=creation(GetCurrentProcess());
    memcpy(p.s->epoch,epoch,33);atomic_init(&p.s->acked,0);atomic_init(&p.s->published,0);atomic_init(&p.s->state,ACTIVE);
    atomic_init(&p.gate,0);atomic_init(&p.inputs,0);atomic_init(&p.original_calls,0);atomic_init(&p.errors,0);
    for(unsigned i=0;i<CAPACITY;i++){
        atomic_init(&p.s->records[i].stamp,0);atomic_init(&p.s->records[i].seq,0);
        for(unsigned j=0;j<4;j++)atomic_init(&p.s->records[i].word[j],0);
    }
    p.s->magic=MAGIC;if(!integrated_setup())return error("setup",22);
    service_stop=CreateEventW(NULL,TRUE,FALSE,NULL);work_stop=CreateEventW(NULL,TRUE,FALSE,NULL);pipe_event=CreateEventW(NULL,TRUE,FALSE,NULL);
    ack_held=CreateEventW(NULL,TRUE,FALSE,NULL);ack_release=CreateEventW(NULL,TRUE,FALSE,NULL);
    char pipename[128];pipe_name(pipename,name);
    pipe_server=CreateNamedPipeA(pipename,PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED|FILE_FLAG_FIRST_PIPE_INSTANCE,PIPE_TYPE_MESSAGE|PIPE_READMODE_MESSAGE|PIPE_WAIT|PIPE_REJECT_REMOTE_CLIENTS,1,4096,4096,0,NULL);
    if(!service_stop||!work_stop||!pipe_event||!ack_held||!ack_release||pipe_server==INVALID_HANDLE_VALUE)return error("service_setup",26);
    service_thread=CreateThread(NULL,0,ack_service,&p,0,NULL);if(!service_thread)return error("service_thread",26);
    printf("{\"event\":\"ready\",\"pid\":%lu,\"created\":%llu,\"registered_entries\":3,\"worker_autonomous\":true}\n",GetCurrentProcessId(),(unsigned long long)p.s->created);
    char line[160];
    while(fgets(line,sizeof line,stdin)){
        unsigned count=0,delay=0,pid=0;unsigned long long created=0;char scenario_name[48];
        if(!strcmp(line,"quit\n"))break;
        else if(!strcmp(line,"resume\n")){run_race_finish();integrated_status(&p);}
        else if(race_open)puts("{\"ok\":false,\"reason\":\"race_open\"}");
        else if(sscanf(line,"bind %u %llu",&pid,&created)==2)bind_peer(pid,created);
        else if(sscanf(line,"work %u %u",&count,&delay)==2&&count<=1000000&&delay<=100&&!work_thread){
            work_count=count;work_delay=delay;work_thread=CreateThread(NULL,0,automatic_work,&p,0,NULL);
            if(!work_thread)return error("worker",27);puts("{\"event\":\"started\"}");
        }else if(!strcmp(line,"join\n")){if(!finish_work())return error("join",27);integrated_status(&p);}
        else if(!strcmp(line,"ack_hold\n")){ResetEvent(ack_held);ResetEvent(ack_release);InterlockedExchange(&pause_ack,1);puts("{\"ok\":true}");}
        else if(!strcmp(line,"ack_held\n")){printf("{\"ok\":%s}\n",WaitForSingleObject(ack_held,5000)==WAIT_OBJECT_0?"true":"false");}
        else if(!strcmp(line,"ack_release\n")){SetEvent(ack_release);puts("{\"ok\":true}");}
        else if(!strcmp(line,"publisher_hold\n")&&!work_thread){atomic_store(&p.gate,1);publisher_held=1;puts("{\"ok\":true}");}
        else if(!strcmp(line,"publisher_release\n")){if(publisher_held)atomic_store(&p.gate,0);publisher_held=0;puts("{\"ok\":true}");}
        else if(!strcmp(line,"transport\n"))printf("{\"accepted\":%llu,\"rejected\":%llu,\"peer_pid\":%u}\n",(unsigned long long)atomic_load(&acks_ok),(unsigned long long)atomic_load(&acks_rejected),atomic_load(&peer_pid));
        else if(sscanf(line,"race %47s",scenario_name)==1&&!work_thread){run_race_start(scenario_name);integrated_status(&p);}
        else if(sscanf(line,"scenario %47s",scenario_name)==1&&!work_thread)run_scenario(&p,scenario_name);
        else if(sscanf(line,"call %u %u",&count,&delay)==2&&count<=1000000&&!work_thread){for(unsigned i=0;i<count;i++)integrated_call(&p,delay);integrated_status(&p);}
        else if(!strcmp(line,"status\n"))integrated_status(&p);
        else if(!strcmp(line,"stop\n")){fault(&p,STOPPED);integrated_status(&p);}
        else puts("{\"event\":\"error\",\"reason\":\"command\"}");
    }
    run_race_finish();SetEvent(work_stop);SetEvent(ack_release);SetEvent(service_stop);
    int joined=finish_work()&&WaitForSingleObject(service_thread,8000)==WAIT_OBJECT_0;
    if(!joined)return error("exit_join",27);
    atomic_store(&p.s->state,EXITING);
    int restored=integrated_patch(0)&&!memcmp(page+0x100,prefix,5);
    int deleted=RtlDeleteFunctionTable(integrated_table)!=0,absent=1;
    for(int i=0;i<3;i++){DWORD64 base=0;if(RtlLookupFunctionEntry((DWORD64)(uintptr_t)(page+integrated_table[i].BeginAddress),&base,NULL))absent=0;}
    int freed=deleted&&VirtualFree(page,0,MEM_RELEASE)!=0;
    int closed=UnmapViewOfFile(p.s)&&CloseHandle(p.mapping),guard_freed=VirtualFree(guard_memory,0,MEM_RELEASE)!=0;
    HANDLE handles[]={pipe_server,pipe_event,service_stop,work_stop,service_thread,ack_held,ack_release};for(unsigned i=0;i<7;i++)closed=CloseHandle(handles[i])&&closed;
    if(bound_peer)closed=CloseHandle(bound_peer)&&closed;
    printf("{\"event\":\"bye\",\"prefix_restored\":%s,\"table_deleted\":%s,\"lookups_absent\":%s,\"freed\":%s,\"mapping_closed\":%s,\"guard_freed\":%s,\"threads_joined\":true}\n",restored?"true":"false",deleted?"true":"false",absent?"true":"false",freed?"true":"false",closed?"true":"false",guard_freed?"true":"false");
    return restored&&deleted&&absent&&freed&&closed&&guard_freed?0:23;
}
/* Independent read variant, with a split header-load probe for concurrency. */
static void autonomous_copy(RingConsumer *c,uint64_t a){
    c->count=0;c->reason=ring_live(c);if(strcmp(c->reason,"ok"))return;
    uint64_t n=atomic_load(&c->s->published);
    if(!skip_cursor&&atomic_load(&c->s->acked)!=a){c->reason="changed";return;}
    if(a>n||n-a>CAPACITY||n>MAX_SEQUENCE){c->reason="layout";return;}
    for(uint64_t seq=a+1;seq<=n;seq++){
        const Record *r=&c->s->records[(seq-1)%CAPACITY];Snapshot *s=&c->pending[c->count];
        uint64_t before=atomic_load(&r->stamp);s->seq=atomic_load(&r->seq);
        c->reason=ring_copy_tail(r,s,before,seq);if(strcmp(c->reason,"ok")){c->count=0;return;}
        c->count++;
    }
    c->reason=ring_live(c);
}
static int bridge_main(const char *name,const char *epoch,uint32_t pid,uint64_t created){
    RingConsumer c={0};int result=0;HANDLE pipe=INVALID_HANDLE_VALUE;
    c.mapping=OpenFileMappingA(FILE_MAP_READ,FALSE,name);if(!c.mapping)return error("mapping",11);
    c.s=MapViewOfFile(c.mapping,FILE_MAP_READ,0,0,sizeof(Shared));if(!c.s){CloseHandle(c.mapping);return error("map",11);}
    if(c.s->magic!=MAGIC||c.s->version!=2||c.s->bytes!=sizeof(Shared)||memcmp(c.s->epoch,epoch,33)||c.s->pid!=pid||c.s->created!=created){result=error("expected_target",11);goto done;}
    c.process=OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
    if(!c.process||creation(c.process)!=created){result=error("expected_target",11);goto done;}
    MEMORY_BASIC_INFORMATION mbi;if(!VirtualQuery(c.s,&mbi,sizeof mbi)||mbi.Protect!=PAGE_READONLY){result=error("read_only",11);goto done;}
    char pipename[128];pipe_name(pipename,name);
    for(unsigned i=0;i<500;i++){pipe=CreateFileA(pipename,GENERIC_READ|GENERIC_WRITE,0,NULL,OPEN_EXISTING,0,NULL);if(pipe!=INVALID_HANDLE_VALUE)break;Sleep(10);}
    if(pipe==INVALID_HANDLE_VALUE){result=error("pipe_connect",11);goto done;}
    ULONG server_pid=0;
    if(!GetNamedPipeServerProcessId(pipe,&server_pid)||server_pid!=pid||WaitForSingleObject(c.process,0)!=WAIT_TIMEOUT){result=error("pipe_server_binding",11);goto done;}
    printf("{\"event\":\"ready\",\"read_only\":true,\"pid\":%lu,\"created\":%llu}\n",GetCurrentProcessId(),(unsigned long long)creation(GetCurrentProcess()));
    char line[160];uint64_t cursor_a=0;int cursor_open=0;
    while(fgets(line,sizeof line,stdin)){
        AckPacket a={0};a.magic=MAGIC;a.pid=pid;a.created=created;unsigned long long seq=0,gen=0,as_created=0;unsigned as_pid=0;
        int as=sscanf(line,"ack_as %32s %llu %llu %u %llu",a.epoch,&seq,&gen,&as_pid,&as_created)==5;
        if(!strcmp(line,"read\n")){autonomous_copy(&c,atomic_load(&c.s->acked));ring_emit(&c);}
        else if(!strcmp(line,"cursor_begin\n")){cursor_a=atomic_load(&c.s->acked);cursor_open=1;puts("{\"ok\":true}");}
        else if(!strcmp(line,"cursor_end\n")&&cursor_open){autonomous_copy(&c,cursor_a);cursor_open=0;ring_emit(&c);}
        else if(as||sscanf(line,"ack %32s %llu %llu",a.epoch,&seq,&gen)==3){
            a.seq=seq;a.generation=gen;if(as){a.pid=as_pid;a.created=as_created;}
            DWORD bytes=0;AckReply reply={0};
            if(!WriteFile(pipe,&a,sizeof a,&bytes,NULL)||bytes!=sizeof a||!ReadFile(pipe,&reply,sizeof reply,&bytes,NULL)||bytes!=sizeof reply){result=error("ack_io",28);break;}
            const char *reasons[]={"ok","binding","busy","invalid","stale","hold_timeout"};
            printf("{\"event\":\"ack\",\"ok\":%s,\"acked\":%llu,\"reason\":\"%s\"}\n",reply.ok?"true":"false",(unsigned long long)reply.acked,reply.reason<6?reasons[reply.reason]:"protocol");
        }else if(!strcmp(line,"quit\n"))break;
        else puts("{\"event\":\"error\",\"reason\":\"command\"}");
    }
done:
    if(pipe!=INVALID_HANDLE_VALUE)CloseHandle(pipe);if(c.process)CloseHandle(c.process);UnmapViewOfFile(c.s);CloseHandle(c.mapping);
    if(!result)puts("{\"event\":\"bye\"}");return result;
}
int main(int argc,char **argv){
    /* Retained frozen harness entry points are not dispatched by this main. */
    (void)consumer;(void)integrated_target;
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);setvbuf(stdout,NULL,_IONBF,0);
    if(argc<4||strlen(argv[2])>80||strncmp(argv[2],"Local\\VXOwnPublisher-",21)||!valid_epoch(argv[3]))return error("arguments",12);
    if(!strcmp(argv[1],"bridge")&&(argc==6||argc==7)){if(argc==7){if(strcmp(argv[6],"skip_cursor"))return error("mode",12);skip_cursor=1;}return bridge_main(argv[2],argv[3],(uint32_t)strtoul(argv[4],NULL,10),strtoull(argv[5],NULL,10));}
    if(strcmp(argv[1],"target")||(argc!=4&&argc!=5))return error("role",12);
    if(argc==5){if(!strcmp(argv[4],"skip_peer"))skip_peer=1;else if(!strcmp(argv[4],"skip_target_binding"))skip_target_binding=1;else if(!strcmp(argv[4],"skip_epoch"))skip_epoch=1;else if(!strcmp(argv[4],"skip_cursor"))skip_cursor=1;else if(!strcmp(argv[4],"late_stop"))late_stop=1;else if(!strcmp(argv[4],"skip_recheck"))skip_recheck=1;else return error("mode",12);}
    return autonomous_target(argv[2],argv[3]);
}
