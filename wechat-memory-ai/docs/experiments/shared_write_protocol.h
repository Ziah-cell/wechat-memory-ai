/* Owned-process Windows x64 protocol v3. Never mapped into a real application. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { ACTIVE=1, STOPPED, EXITING, FULL, BUSY, INVALID };
enum { CAPACITY=8, PAYLOAD=32, MAGIC=0x56585232 };
#define MAX_SEQUENCE ((UINT64_C(1)<<62)-1)
typedef struct { _Atomic uint64_t stamp, seq, word[4]; } Record;
typedef struct {
    uint32_t magic,version,bytes,pid;
    uint64_t created;
    char epoch[33];
    _Atomic uint32_t state;
    _Atomic uint64_t published,acked;
    _Alignas(4096) Record records[CAPACITY];
} Shared;
typedef struct {
    HANDLE mapping;
    Shared *s;
    _Atomic uint32_t gate;
    _Atomic uint64_t inputs,original_calls,errors;
} Publisher;
_Static_assert(sizeof(Shared)==8192,"two bounded pages");
_Static_assert(offsetof(Shared,records)==4096,"record/control isolation");
_Static_assert(ATOMIC_LLONG_LOCK_FREE==2&&ATOMIC_INT_LOCK_FREE==2,"native atomics");
static int overwrite,skip_epoch,skip_generation,skip_stamp;
static int error(const char *reason,int code){printf("{\"event\":\"error\",\"reason\":\"%s\",\"win32\":%lu}\n",reason,GetLastError());return code;}
static uint64_t creation(HANDLE process){FILETIME c,e,k,u;if(!GetProcessTimes(process,&c,&e,&k,&u))return 0;return ((uint64_t)c.dwHighDateTime<<32)|c.dwLowDateTime;}
static int valid_epoch(const char *s){if(strlen(s)!=32)return 0;for(unsigned i=0;i<32;i++)if(!strchr("0123456789abcdef",s[i]))return 0;return 1;}
static void fault(Publisher *p,uint32_t reason){uint32_t active=ACTIVE;atomic_compare_exchange_strong(&p->s->state,&active,reason);}

/* Control-plane ACKs are forwarded by the trusted fixture controller ONLY
 * after the ledger emits its post-COMMIT receipt. This is not authentication. */
static void acknowledge(Publisher *p,const char *epoch,uint64_t seq,uint64_t generation){
    uint32_t free_gate=0;
    if(!atomic_compare_exchange_strong(&p->gate,&free_gate,1)){puts("{\"event\":\"ack\",\"ok\":false,\"reason\":\"busy\"}");return;}
    int valid=(!strcmp(epoch,p->s->epoch)||skip_epoch)&&seq>atomic_load(&p->s->acked)&&
        seq<=atomic_load(&p->s->published)&&seq<=MAX_SEQUENCE&&
        (generation==(seq-1)/CAPACITY+1||skip_generation)&&
        atomic_load(&p->s->records[(seq-1)%CAPACITY].stamp)==seq*2;
    if(valid)atomic_store(&p->s->acked,seq);
    atomic_store(&p->gate,0);
    printf("{\"event\":\"ack\",\"ok\":%s,\"acked\":%llu}\n",valid?"true":"false",(unsigned long long)atomic_load(&p->s->acked));
}

typedef struct {uint64_t seq,word[4];} Snapshot;
typedef struct {HANDLE mapping,process;const Shared *s;Snapshot pending[CAPACITY];unsigned count;uint64_t split_stamp;int split_open;const char *reason;} RingConsumer;
static const char *ring_live(RingConsumer *c){
    DWORD alive=WaitForSingleObject(c->process,0);
    if(alive==WAIT_OBJECT_0)return "target_dead";
    if(alive!=WAIT_TIMEOUT)return "process_query_failed";
    uint32_t state=atomic_load(&c->s->state);
    if(state!=ACTIVE&&state!=FULL&&state!=BUSY&&state!=STOPPED)return "inactive";
    return "ok";
}
/* Normal and split reads share this exact validation boundary. All shared
 * fields use seq_cst atomics: observing any new word orders the final stamp
 * after the writer's odd stamp. A complete old copy remains safe to replay. */
static const char *ring_copy_tail(const Record *r,Snapshot *s,uint64_t before,uint64_t expected_seq){
    for(unsigned j=0;j<4;j++)s->word[j]=atomic_load(&r->word[j]);
    uint64_t after=atomic_load(&r->stamp);
    if(!skip_stamp&&(before!=expected_seq*2||after!=before||s->seq!=expected_seq))return "changed";
    uint64_t id=s->word[0];
    if(s->word[1]!=(id^0xa5a5a5a5ULL)||s->word[2]!=id+7||s->word[3]!=id*3)return "record";
    return "ok";
}
static void ring_copy(RingConsumer *c){
    c->count=0;c->reason=ring_live(c);if(strcmp(c->reason,"ok"))return;
    uint64_t a=atomic_load(&c->s->acked),n=atomic_load(&c->s->published);
    if(a>n||n-a>CAPACITY||n>MAX_SEQUENCE){c->reason="layout";return;}
    for(uint64_t seq=a+1;seq<=n;seq++){
        const Record *r=&c->s->records[(seq-1)%CAPACITY];Snapshot *s=&c->pending[c->count];
        uint64_t before=atomic_load(&r->stamp);s->seq=atomic_load(&r->seq);
        c->reason=ring_copy_tail(r,s,before,seq);
        if(strcmp(c->reason,"ok")){c->count=0;return;}
        c->count++;
    }
    c->reason=ring_live(c);
}
static void ring_emit(RingConsumer *c){
    if(!strcmp(c->reason,"ok"))c->reason=ring_live(c);
    if(strcmp(c->reason,"ok"))c->count=0;
    printf("{\"event\":\"read\",\"reason\":\"%s\",\"records\":[",c->reason);
    for(unsigned i=0;i<c->count;i++){
        Snapshot *r=&c->pending[i];
        printf("%s{\"seq\":%llu,\"generation\":%llu,\"id\":%llu,\"a\":%llu,\"b\":%llu,\"c\":%llu}",i?",":"",(unsigned long long)r->seq,(unsigned long long)((r->seq-1)/CAPACITY+1),(unsigned long long)r->word[0],(unsigned long long)r->word[1],(unsigned long long)r->word[2],(unsigned long long)r->word[3]);
    }
    puts("]}");c->count=0;
}
/* Deterministic read/reuse interleave, confined to the owned test consumer. */
static void ring_split(RingConsumer *c){
    c->count=0;c->reason=ring_live(c);
    uint64_t seq=atomic_load(&c->s->acked)+1;
    if(strcmp(c->reason,"ok")||seq>atomic_load(&c->s->published)){puts("{\"event\":\"error\"}");return;}
    const Record *r=&c->s->records[(seq-1)%CAPACITY];
    c->split_stamp=atomic_load(&r->stamp);c->pending[0].seq=atomic_load(&r->seq);
    c->split_open=1;puts("{\"event\":\"split\"}");
}
static void ring_finish(RingConsumer *c){
    if(!c->split_open){c->reason="no_copy";ring_emit(c);return;}
    c->split_open=0;Snapshot *s=&c->pending[0];const Record *r=&c->s->records[(s->seq-1)%CAPACITY];
    c->count=1;c->reason=ring_copy_tail(r,s,c->split_stamp,s->seq);
    ring_emit(c);
}
static int consumer(const char *name,const char *epoch){
    RingConsumer c={0};int result=0;
    c.mapping=OpenFileMappingA(FILE_MAP_READ,FALSE,name);if(!c.mapping)return error("open_mapping",11);
    c.s=MapViewOfFile(c.mapping,FILE_MAP_READ,0,0,sizeof(Shared));if(!c.s){CloseHandle(c.mapping);return error("map_consumer",11);}
    if(c.s->magic!=MAGIC||c.s->version!=3||c.s->bytes!=sizeof(Shared)||memcmp(c.s->epoch,epoch,33)){result=error("binding",11);goto done;}
    c.process=OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,c.s->pid);
    if(!c.process||creation(c.process)!=c.s->created){result=error("process_binding",11);goto done;}
    MEMORY_BASIC_INFORMATION mbi;
    if(!VirtualQuery(c.s,&mbi,sizeof(mbi))||mbi.Protect!=PAGE_READONLY){result=error("read_only",11);goto done;}
    puts("{\"event\":\"ready\",\"read_only\":true}");
    char line[128];
    while(fgets(line,sizeof(line),stdin)){
        if(!strcmp(line,"read\n")){ring_copy(&c);ring_emit(&c);}
        else if(!strcmp(line,"split\n"))ring_split(&c);
        else if(!strcmp(line,"finish\n"))ring_finish(&c);
        else if(!strcmp(line,"quit\n"))break;
        else puts("{\"event\":\"error\",\"reason\":\"command\"}");
    }
done:
    if(c.process)CloseHandle(c.process);
    UnmapViewOfFile(c.s);CloseHandle(c.mapping);if(!result)puts("{\"event\":\"bye\"}");return result;
}
