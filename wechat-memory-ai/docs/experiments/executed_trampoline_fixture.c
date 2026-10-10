/* Owned executable and generated allocation only. No external PID interface. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <inttypes.h>

typedef uint64_t (*IntFunction)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
typedef double (*FloatFunction)(double,double,double,double,double,double);
extern uint64_t register_caller(IntFunction fn, uint64_t first);
static IntFunction int_trampoline, int_entry;
static FloatFunction float_trampoline;
static volatile LONG capturing, hook_entries, hook_returns, captures, worker_errors;
static BYTE *page;
static DWORD integer_size;
static const BYTE prefix[] = {0x55,0x41,0x56,0x56,0x57};

__declspec(noinline) static uint64_t int_hook(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {
    InterlockedIncrement(&hook_entries);
    if (InterlockedCompareExchange(&capturing,0,0)) InterlockedIncrement(&captures);
    uint64_t result=int_trampoline(a,b,c,d,e,f);
    InterlockedIncrement(&hook_returns);
    return result;
}
__declspec(noinline) static double float_hook(double a,double b,double c,double d,double e,double f) {
    InterlockedIncrement(&hook_entries);
    if (InterlockedCompareExchange(&capturing,0,0)) InterlockedIncrement(&captures);
    double result=float_trampoline(a,b,c,d,e,f);
    InterlockedIncrement(&hook_returns);
    return result;
}
static uint64_t expected(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {
    return a+3*b+5*c+7*d+11*e+13*f;
}
static void append(BYTE *dst, DWORD *len, const BYTE *src, size_t count) {
    memcpy(dst+*len,src,count); *len+=(DWORD)count;
}
static void multiply_float(BYTE *dst, DWORD *len, unsigned reg, unsigned weight) {
    BYTE instruction[]={0xf2,0x0f,0x59,(BYTE)(0x05|(reg<<3)),0,0,0,0};
    int32_t delta=(int32_t)((page+0x900+8*weight)-(dst+*len+sizeof instruction));
    memcpy(instruction+4,&delta,4);append(dst,len,instruction,sizeof instruction);
    BYTE add[]={0xf2,0x0f,0x58,(BYTE)(0xc0|reg)};
    append(dst,len,add,sizeof add);
}
static DWORD original(BYTE *dst, int floating) {
    DWORD len=0;
    const BYTE prologue[]={0x55,0x41,0x56,0x56,0x57,0x48,0x83,0xec,0x08};
    const BYTE clobber[]={0xbd,0x22,0x22,0x11,0x11,0x41,0xbe,0x44,0x44,0x33,0x33,
                         0xbe,0x66,0x66,0x55,0x55,0xbf,0x88,0x88,0x77,0x77};
    const BYTE integer_body[]={
        0x48,0x85,0xc9,0x75,0x05,0x31,0xc0,0x48,0x8b,0x00,
        0x48,0x89,0xc8,0x48,0x6b,0xd2,0x03,0x48,0x01,0xd0,
        0x4d,0x6b,0xc0,0x05,0x4c,0x01,0xc0,
        0x4d,0x6b,0xc9,0x07,0x4c,0x01,0xc8,
        0x4c,0x8b,0x54,0x24,0x50,0x4d,0x6b,0xd2,0x0b,0x4c,0x01,0xd0,
        0x4c,0x8b,0x5c,0x24,0x58,0x4d,0x6b,0xdb,0x0d,0x4c,0x01,0xd8};
    const BYTE epilogue[]={0x48,0x83,0xc4,0x08,0x5f,0x5e,0x41,0x5e,0x5d,0xc3};
    append(dst,&len,prologue,sizeof prologue);append(dst,&len,clobber,sizeof clobber);
    if(floating) {
        for(unsigned reg=1;reg<=3;reg++) multiply_float(dst,&len,reg,reg-1);
        const BYTE load_e[]={0xf2,0x0f,0x10,0x64,0x24,0x50};
        const BYTE load_f[]={0xf2,0x0f,0x10,0x6c,0x24,0x58};
        append(dst,&len,load_e,sizeof load_e);multiply_float(dst,&len,4,3);
        append(dst,&len,load_f,sizeof load_f);multiply_float(dst,&len,5,4);
    } else append(dst,&len,integer_body,sizeof integer_body);
    append(dst,&len,epilogue,sizeof epilogue);
    return len;
}
static DWORD jump_absolute(BYTE *dst, uintptr_t target) {
    dst[0]=0x49;dst[1]=0xbb;memcpy(dst+2,&target,8);
    dst[10]=0x41;dst[11]=0xff;dst[12]=0xe3;
    return 13;
}
static void function_entry(RUNTIME_FUNCTION *entry,DWORD begin,DWORD size,DWORD unwind) {
    entry->BeginAddress=begin;entry->EndAddress=begin+size;entry->UnwindData=unwind;
}
static int patch_entries(int install) {
    DWORD prior;
    if (!VirtualProtect(page,4096,PAGE_READWRITE,&prior)) return 0;
    for (DWORD start=0x100;start<=0x500;start+=0x400) {
        if (install) {
            int32_t delta=0x300-0x100-5;
            page[start]=0xe9;memcpy(page+start+1,&delta,4);
        } else memcpy(page+start,prefix,sizeof prefix);
    }
    DWORD ignored;
    if (!VirtualProtect(page,4096,PAGE_EXECUTE_READ,&ignored)) return 0;
    return FlushInstructionCache(GetCurrentProcess(),page,4096)!=0;
}
static LONG exception_filter(EXCEPTION_POINTERS *ep) {
    uintptr_t at=(uintptr_t)ep->ExceptionRecord->ExceptionAddress;
    int inside=at>=(uintptr_t)(page+0x100) && at<(uintptr_t)(page+0x100+integer_size);
    int av=ep->ExceptionRecord->ExceptionCode==EXCEPTION_ACCESS_VIOLATION;
    printf("{\"event\":\"filter\",\"in_original\":%s,\"access_violation\":%s}\n",inside?"true":"false",av?"true":"false");
    return inside && av ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH;
}
/* Observe only the known fault in our own generated body. Never alter OS context. */
static LONG CALLBACK observe_fault(EXCEPTION_POINTERS *ep) {
    uintptr_t at=(uintptr_t)ep->ExceptionRecord->ExceptionAddress;
    if(ep->ExceptionRecord->ExceptionCode!=EXCEPTION_ACCESS_VIOLATION ||
       at<(uintptr_t)(page+0x100) || at>=(uintptr_t)(page+0x100+integer_size)) return EXCEPTION_CONTINUE_SEARCH;
    CONTEXT copy=*ep->ContextRecord;
    uint64_t saved[5];memcpy(saved,(const void *)(uintptr_t)(copy.Rsp+8),sizeof saved);
    DWORD64 base=0;PRUNTIME_FUNCTION fn=RtlLookupFunctionEntry(copy.Rip,&base,NULL);
    unsigned mask=0;uint64_t initial_rsp=copy.Rsp;
    if(fn && base==(DWORD64)(uintptr_t)page) {
        PVOID handler_data=NULL;DWORD64 frame=0;
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,copy.Rip,fn,&copy,&handler_data,&frame,NULL);
        if(copy.Rbp==saved[3]) mask|=1;
        if(copy.R14==saved[2]) mask|=2;
        if(copy.Rsi==saved[1]) mask|=4;
        if(copy.Rdi==saved[0]) mask|=8;
        if(copy.Rsp==initial_rsp+48) mask|=16;
        if(copy.Rip==saved[4]) mask|=32;
    }
    printf("{\"event\":\"fault_unwind\",\"restored_mask\":%u,\"rsp_delta\":%" PRIu64 "}\n",mask,(uint64_t)(copy.Rsp-initial_rsp));
    return EXCEPTION_CONTINUE_SEARCH;
}
__declspec(noinline) static DWORD invoke_fault(IntFunction fn, uint64_t *mask) {
    DWORD caught=0;
    __try { *mask=register_caller(fn,0); }
    __except(exception_filter(GetExceptionInformation())) { caught=GetExceptionCode(); }
    *mask=register_caller(fn,1);
    return caught;
}
static DWORD WINAPI worker(LPVOID param) {
    uint64_t seed=(uintptr_t)param;
    for (uint64_t i=1;i<=5000;i++) {
        uint64_t a=0xf123456700000000ULL+seed*10000+i;
        uint64_t b=i*3,c=0x123456780ULL+i,d=i*7,e=i*11,f=~i;
        if(int_entry(a,b,c,d,e,f)!=expected(a,b,c,d,e,f)) InterlockedIncrement(&worker_errors);
    }
    return 0;
}
int main(int argc,char **argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
    setvbuf(stdout,NULL,_IONBF,0);
    if(argc!=4) return 2;
    int integer=!strcmp(argv[1],"integer"),floating=!strcmp(argv[1],"floating");
    int fault=!strcmp(argv[1],"fault"),parallel=!strcmp(argv[1],"parallel"),transition=!strcmp(argv[1],"transition");
    int baseline=!strcmp(argv[2],"baseline"),hooked=!strcmp(argv[2],"hooked"),stopped=!strcmp(argv[2],"stopped");
    int omit=!strcmp(argv[3],"omit_rbp");
    if(!(integer||floating||fault||parallel||transition)||!(baseline||hooked||stopped)||(!omit&&strcmp(argv[3],"exact"))||(transition&&!stopped)) return 2;
    page=VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if(!page) return 3;
    const double weights[]={3,5,7,11,13};memcpy(page+0x900,weights,sizeof weights);
    integer_size=original(page+0x100,0);DWORD float_size=original(page+0x500,1);
    memcpy(page+0x200,prefix,5);jump_absolute(page+0x205,(uintptr_t)(page+0x105));
    memcpy(page+0x600,prefix,5);jump_absolute(page+0x605,(uintptr_t)(page+0x505));
    jump_absolute(page+0x300,(uintptr_t)int_hook);jump_absolute(page+0x700,(uintptr_t)float_hook);
    const BYTE original_unwind[]={1,9,5,0,9,2,5,0x70,4,0x60,3,0xe0,1,0x50,0,0};
    const BYTE trampoline_unwind[]={1,18,4,0,5,0x70,4,0x60,3,0xe0,1,0x50};
    const BYTE leaf_unwind[]={1,0,0,0};
    memcpy(page+0x800,original_unwind,sizeof original_unwind);
    memcpy(page+0x820,trampoline_unwind,sizeof trampoline_unwind);
    memcpy(page+0x840,leaf_unwind,sizeof leaf_unwind);
    if(omit) {page[0x802]=4;page[0x80c]=page[0x80d]=0;page[0x822]=3;page[0x82a]=page[0x82b]=0;}
    RUNTIME_FUNCTION table[6];
    function_entry(&table[0],0x100,integer_size,0x800);function_entry(&table[1],0x200,18,0x820);
    function_entry(&table[2],0x300,13,0x840);function_entry(&table[3],0x500,float_size,0x800);
    function_entry(&table[4],0x600,18,0x820);function_entry(&table[5],0x700,13,0x840);
    DWORD prior;
    if(!VirtualProtect(page,4096,PAGE_EXECUTE_READ,&prior)||!FlushInstructionCache(GetCurrentProcess(),page,4096)) return 4;
    if(!RtlAddFunctionTable(table,6,(DWORD64)(uintptr_t)page)) return 5;
    int matches=1;
    for(int i=0;i<6;i++) {
        DWORD64 base=0;PRUNTIME_FUNCTION found=RtlLookupFunctionEntry((DWORD64)(uintptr_t)(page+table[i].BeginAddress),&base,NULL);
        if(found!=&table[i]||base!=(DWORD64)(uintptr_t)page) matches=0;
    }
    printf("{\"event\":\"ready\",\"registered_entries\":6,\"all_lookups_match\":%s}\n",matches?"true":"false");
    if(!matches) return 6;
    int_entry=(IntFunction)(uintptr_t)(page+0x100);int_trampoline=(IntFunction)(uintptr_t)(page+0x200);
    FloatFunction float_entry=(FloatFunction)(uintptr_t)(page+0x500);float_trampoline=(FloatFunction)(uintptr_t)(page+0x600);
    if(!baseline && !patch_entries(1)) return 7;
    InterlockedExchange(&capturing,hooked);
    uint64_t mask=0;DWORD caught=0;LONG errors=0;
    if(fault) {
        PVOID observer=AddVectoredExceptionHandler(1,observe_fault);
        if(!observer) return 10;
        caught=invoke_fault(int_entry,&mask);
        if(!RemoveVectoredExceptionHandler(observer)) errors++;
    }
    else {
        if(transition) {
            InterlockedExchange(&capturing,1);
            if(register_caller(int_entry,1)!=31) errors++;
            InterlockedExchange(&capturing,0);
        }
        if(floating) for(int i=0;i<128;i++) {
            double a=i*.5,b=-i*.25,c=i+3.0,d=2.0-i,e=i*.125,f=91.5-i;
            if(float_entry(a,b,c,d,e,f)!=a+3*b+5*c+7*d+11*e+13*f) errors++;
        }
        if(parallel) {
            HANDLE workers[4];int created=0;
            for(int i=0;i<4;i++) {HANDLE h=CreateThread(NULL,0,worker,(LPVOID)(uintptr_t)(i+1),0,NULL);if(!h){errors++;break;}workers[created++]=h;}
            for(int i=0;i<created;i++) {
                if(WaitForSingleObject(workers[i],INFINITE)!=WAIT_OBJECT_0) return 8;
                DWORD code=1;if(!GetExitCodeThread(workers[i],&code)||code) errors++;
                if(!CloseHandle(workers[i])) errors++;
            }
            errors+=InterlockedCompareExchange(&worker_errors,0,0);
        }
        mask=register_caller(int_entry,1);
    }
    printf("{\"event\":\"result\",\"errors\":%ld,\"register_mask\":%" PRIu64 ",\"hook_entries\":%ld,\"hook_returns\":%ld,\"captures\":%ld,\"caught\":%lu,\"installed\":%s}\n",
           errors,mask,hook_entries,hook_returns,captures,caught,baseline?"false":"true");
    int restored=patch_entries(0)&&!memcmp(page+0x100,prefix,5)&&!memcmp(page+0x500,prefix,5);
    int deleted=RtlDeleteFunctionTable(table)!=0,absent=1;
    for(int i=0;i<6;i++){DWORD64 base=0;if(RtlLookupFunctionEntry((DWORD64)(uintptr_t)(page+table[i].BeginAddress),&base,NULL)) absent=0;}
    int freed=VirtualFree(page,0,MEM_RELEASE)!=0;
    printf("{\"event\":\"cleanup\",\"prefix_restored\":%s,\"table_deleted\":%s,\"lookups_absent\":%s,\"freed\":%s}\n",
           restored?"true":"false",deleted?"true":"false",absent?"true":"false",freed?"true":"false");
    return errors||mask!=31||!restored||!deleted||!absent||!freed ? 9:0;
}
