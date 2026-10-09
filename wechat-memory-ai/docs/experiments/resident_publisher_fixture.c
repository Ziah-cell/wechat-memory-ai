/* Windows x64 own-process experiment, NOT a hook or a production message source.
 * The target links its publisher at startup. Consumers own no target resources.
 * Single-session append-only records: no ACKs, overwrite, reset or buffer reuse.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { ACTIVE=1, STOPPED, EXITING, FULL, BUSY, INVALID };
enum { CAPACITY=8, PAYLOAD=32, MAGIC=0x56585031 };
typedef struct { uint64_t seq, word[4]; } Record;
typedef struct {
    uint32_t magic, version, bytes, pid;
    uint64_t created;
    char epoch[33];
    _Atomic uint32_t state;
    _Atomic uint64_t published;
    Record records[CAPACITY];
} Shared;
typedef struct {
    HANDLE mapping;
    Shared *s;
    _Atomic uint32_t gate;
    _Atomic uint64_t inputs, original_calls, errors;
} Publisher;
typedef struct { Publisher *p; HANDLE start; unsigned count, delay; } Worker;

_Static_assert(sizeof(Record)==40, "record layout");
_Static_assert(sizeof(Shared)<4096, "one bounded page");
_Static_assert(ATOMIC_LLONG_LOCK_FREE==2 && ATOMIC_INT_LOCK_FREE==2, "native atomic operations required");

static int error(const char *reason, int code) {
    printf("{\"event\":\"error\",\"reason\":\"%s\",\"win32\":%lu}\n", reason, GetLastError());
    return code;
}
static uint64_t creation(HANDLE process) {
    FILETIME c,e,k,u;
    if (!GetProcessTimes(process,&c,&e,&k,&u)) return 0;
    return ((uint64_t)c.dwHighDateTime<<32)|c.dwLowDateTime;
}
static int valid_epoch(const char *s) {
    if (strlen(s)!=32) return 0;
    for (unsigned i=0;i<32;i++) if (!strchr("0123456789abcdef",s[i])) return 0;
    return 1;
}
static void fault(Publisher *p, uint32_t reason) {
    uint32_t active=ACTIVE;
    atomic_compare_exchange_strong(&p->s->state,&active,reason);
}

/* No waits, allocations, IO, consumer process queries or retry loops here.
 * ptr is ALWAYS a valid local 32-byte fixture object. Bad pointer handling is
 * deliberately not claimed. One failed try-acquire ends this capture session.
 */
static __attribute__((noinline)) void publish(Publisher *p, const uint64_t *ptr, unsigned length) {
    if (atomic_load(&p->s->state)!=ACTIVE) return;
    if (length!=PAYLOAD) { fault(p,INVALID); return; }
    uint32_t free_gate=0;
    if (!atomic_compare_exchange_strong(&p->gate,&free_gate,1)) { fault(p,BUSY); return; }
    if (atomic_load(&p->s->state)==ACTIVE) {
        uint64_t n=atomic_load_explicit(&p->s->published,memory_order_relaxed);
        if (n==CAPACITY) fault(p,FULL);
        else {
            Record *r=&p->s->records[n];
            r->seq=n+1;
            memcpy(r->word,ptr,PAYLOAD);
            /* Record never changes after this release. A concurrent stop can
             * precede this store, but consumers reject the inactive session. */
            atomic_store_explicit(&p->s->published,n+1,memory_order_release);
        }
    }
    atomic_store(&p->gate,0);
}

static __attribute__((noinline)) uint64_t original(Publisher *p, uint64_t input) {
    atomic_fetch_add(&p->original_calls,1);
    return input*5+11;
}
static __attribute__((noinline)) void wrapped(Publisher *p, unsigned length) {
    uint64_t id=atomic_fetch_add(&p->inputs,1)+1;
    uint64_t value[4]={id,id^0xa5a5a5a5ULL,id+7,id*3};
    publish(p,value,length);
    uint64_t result=original(p,id);
    if (result!=id*5+11) atomic_fetch_add(&p->errors,1);
}
static void status(Publisher *p) {
    printf("{\"event\":\"status\",\"state\":%u,\"published\":%llu,\"original\":%llu,\"errors\":%llu}\n",
           atomic_load(&p->s->state),(unsigned long long)atomic_load(&p->s->published),
           (unsigned long long)atomic_load(&p->original_calls),(unsigned long long)atomic_load(&p->errors));
}
static DWORD WINAPI worker_main(void *arg) {
    Worker *w=arg;
    if (WaitForSingleObject(w->start,INFINITE)!=WAIT_OBJECT_0) return 21;
    for (unsigned i=0;i<w->count;i++) {
        wrapped(w->p,PAYLOAD);
        if (w->delay) Sleep(w->delay); /* Workload pacing, OUTSIDE publish. */
    }
    return 0;
}
static int join_workers(HANDLE *threads, unsigned *count, HANDLE *start) {
    for (unsigned i=0;i<*count;i++) {
        DWORD code=1;
        if (WaitForSingleObject(threads[i],8000)!=WAIT_OBJECT_0 ||
            !GetExitCodeThread(threads[i],&code) || code) return 0;
        CloseHandle(threads[i]);
    }
    *count=0;
    if (*start) CloseHandle(*start);
    *start=NULL;
    return 1;
}
static int target(const char *name, const char *epoch) {
    Publisher p={0};
    p.mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,4096,name);
    if (!p.mapping) return error("create_mapping",20);
    if (GetLastError()==ERROR_ALREADY_EXISTS) { CloseHandle(p.mapping); return error("mapping_exists",10); }
    p.s=MapViewOfFile(p.mapping,FILE_MAP_WRITE,0,0,sizeof(Shared));
    if (!p.s) { CloseHandle(p.mapping); return error("map_target",20); }
    memset(p.s,0,sizeof(Shared));
    p.s->version=1; p.s->bytes=sizeof(Shared); p.s->pid=GetCurrentProcessId();
    p.s->created=creation(GetCurrentProcess());
    if (!p.s->created) return error("target_creation",20);
    memcpy(p.s->epoch,epoch,33);
    atomic_init(&p.s->published,0);
    atomic_init(&p.s->state,ACTIVE);
    atomic_init(&p.gate,0); atomic_init(&p.inputs,0);
    atomic_init(&p.original_calls,0); atomic_init(&p.errors,0);
    p.s->magic=MAGIC; /* Consumers only launched after ready by the driver. */
    printf("{\"event\":\"ready\",\"pid\":%lu,\"capacity\":8,\"lock_free\":%s}\n",
           GetCurrentProcessId(),atomic_is_lock_free(&p.s->published)&&atomic_is_lock_free(&p.s->state)?"true":"false");
    char line[128]; HANDLE threads[8]={0},start=NULL; Worker workers[8]; unsigned nthreads=0;
    while (fgets(line,sizeof(line),stdin)) {
        unsigned n=0,len=0,delay=0;
        if (sscanf(line,"call %u %u",&n,&len)==2 && n<=1000000 && !nthreads) {
            for (unsigned i=0;i<n;i++) wrapped(&p,len);
            status(&p);
        } else if (sscanf(line,"workers %u %u %u",&n,&len,&delay)==3 &&
                   n>=1 && n<=8 && len<=1000000 && delay<=10 && !nthreads) {
            start=CreateEventW(NULL,TRUE,FALSE,NULL);
            if (!start) return error("start_event",20);
            for (unsigned i=0;i<n;i++) {
                workers[i]=(Worker){&p,start,len,delay};
                threads[i]=CreateThread(NULL,0,worker_main,&workers[i],0,NULL);
                if (!threads[i]) return error("worker_thread",20);
                nthreads++;
            }
            if (!SetEvent(start)) return error("start_workers",20);
            puts("{\"event\":\"started\"}");
        } else if (!strcmp(line,"join\n")) {
            if (!join_workers(threads,&nthreads,&start)) return error("join",20);
            status(&p);
        } else if (!strcmp(line,"status\n")) status(&p);
        else if (!strcmp(line,"stop\n")) { fault(&p,STOPPED); status(&p); }
        else if (!strcmp(line,"busy\n") && !nthreads) {
            atomic_store(&p.gate,1); wrapped(&p,PAYLOAD); atomic_store(&p.gate,0); status(&p);
        } else if (!strcmp(line,"quit\n")) break;
        else puts("{\"event\":\"error\",\"reason\":\"command\"}");
    }
    atomic_store(&p.s->state,EXITING);
    if (!join_workers(threads,&nthreads,&start)) return error("exit_join",20);
    if (!UnmapViewOfFile(p.s) || !CloseHandle(p.mapping)) return error("close_target",20);
    puts("{\"event\":\"bye\"}");
    return 0;
}

typedef struct {
    HANDLE mapping, process;
    const Shared *s;
    uint64_t cursor;
    Record pending[CAPACITY];
    unsigned count;
    const char *reason;
} Consumer;
static const char *live(Consumer *c) {
    DWORD alive=WaitForSingleObject(c->process,0);
    if (alive==WAIT_OBJECT_0) return "target_dead";
    if (alive!=WAIT_TIMEOUT) return "process_query_failed";
    if (atomic_load(&c->s->state)!=ACTIVE) return "inactive";
    return "ok";
}
static void copy_records(Consumer *c) {
    c->count=0; c->reason=live(c);
    if (strcmp(c->reason,"ok")) return;
    uint64_t n=atomic_load_explicit(&c->s->published,memory_order_acquire);
    if (n>CAPACITY || c->cursor>n) { c->reason="layout"; return; }
    c->count=(unsigned)(n-c->cursor);
    for (unsigned i=0;i<c->count;i++) {
        c->pending[i]=c->s->records[c->cursor+i];
        Record *r=&c->pending[i]; uint64_t id=r->word[0];
        if (r->seq!=c->cursor+i+1 || r->word[1]!=(id^0xa5a5a5a5ULL) ||
            r->word[2]!=id+7 || r->word[3]!=id*3) { c->count=0; c->reason="record"; return; }
    }
    c->reason=live(c);
}
static void commit_records(Consumer *c) {
    if (!strcmp(c->reason,"ok")) c->reason=live(c);
    if (strcmp(c->reason,"ok")) c->count=0;
    /* This final validation is the acceptance boundary, NOT revocable delivery.
     * Stop/death can occur after this line or while stdout is blocked. */
    printf("{\"event\":\"read\",\"reason\":\"%s\",\"records\":[",c->reason);
    for (unsigned i=0;i<c->count;i++) {
        Record *r=&c->pending[i];
        printf("%s{\"seq\":%llu,\"id\":%llu,\"a\":%llu,\"b\":%llu,\"c\":%llu}",i?",":"",
               (unsigned long long)r->seq,(unsigned long long)r->word[0],
               (unsigned long long)r->word[1],(unsigned long long)r->word[2],(unsigned long long)r->word[3]);
    }
    puts("]}"); c->cursor+=c->count; c->count=0; c->reason="no_copy";
}
static int consumer(const char *name, const char *epoch) {
    Consumer c={0}; c.reason="no_copy";
    c.mapping=OpenFileMappingA(FILE_MAP_READ,FALSE,name);
    if (!c.mapping) return error("open_mapping",11);
    c.s=MapViewOfFile(c.mapping,FILE_MAP_READ,0,0,sizeof(Shared));
    if (!c.s) { CloseHandle(c.mapping); return error("map_consumer",11); }
    int result=0;
    if (c.s->magic!=MAGIC || c.s->version!=1 || c.s->bytes!=sizeof(Shared) ||
        memcmp(c.s->epoch,epoch,33)) { result=error("binding",11); goto done; }
    c.process=OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,c.s->pid);
    if (!c.process || creation(c.process)!=c.s->created) { result=error("process_binding",11); goto done; }
    MEMORY_BASIC_INFORMATION mbi;
    if (!VirtualQuery(c.s,&mbi,sizeof(mbi)) || mbi.Protect!=PAGE_READONLY) {
        result=error("read_only_mapping",11); goto done;
    }
    printf("{\"event\":\"ready\",\"target_pid\":%u,\"read_only\":true}\n",c.s->pid);
    char line[128];
    while (fgets(line,sizeof(line),stdin)) {
        if (!strcmp(line,"copy\n")) {
            copy_records(&c);
            printf("{\"event\":\"copied\",\"count\":%u,\"reason\":\"%s\"}\n",c.count,c.reason);
        } else if (!strcmp(line,"commit\n")) commit_records(&c);
        else if (!strcmp(line,"read\n")) { copy_records(&c); commit_records(&c); }
        else if (!strcmp(line,"quit\n")) break;
        else puts("{\"event\":\"error\",\"reason\":\"command\"}");
    }
done:
    if (c.process) CloseHandle(c.process);
    UnmapViewOfFile(c.s); CloseHandle(c.mapping);
    if (!result) puts("{\"event\":\"bye\"}");
    return result;
}
int main(int argc, char **argv) {
    setvbuf(stdout,NULL,_IONBF,0);
    if (argc!=4 || strncmp(argv[2],"Local\\VXOwnPublisher-",21) || !valid_epoch(argv[3]))
        return error("arguments",12);
    if (!strcmp(argv[1],"target")) return target(argv[2],argv[3]);
    if (!strcmp(argv[1],"consumer")) return consumer(argv[2],argv[3]);
    return error("role",12);
}
