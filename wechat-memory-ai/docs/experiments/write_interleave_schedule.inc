/* Controller-driven deterministic fixture; no production scheduling claim. */
static int iw_phase=-1;
static DWORD WINAPI iw_worker(void *arg){
    iw_role=(int)(uintptr_t)arg;scenario=NORMAL;IwDiag *d=&iw_diag[iw_role];d->tid=GetCurrentThreadId();
    if(iw_role==2&&iw_kind==0){race_signal(iw_prepared);race_wait(iw_second_go);}
    integrated_call(integrated_owner,PAYLOAD);d->returned++;
    d->clear=depth_get()==0&&!write_armed&&!write_expected;return 0;
}
static LONG iw_probe_observer(EXCEPTION_POINTERS *ep){
    EXCEPTION_RECORD *r=ep->ExceptionRecord;
    return r->ExceptionCode==EXCEPTION_ACCESS_VIOLATION&&r->ExceptionAddress==&shared_write_site&&r->NumberParameters>=2&&
        r->ExceptionInformation[0]==1&&r->ExceptionInformation[1]==(uintptr_t)iw_first_address?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH;
}
static DWORD WINAPI iw_probe_worker(void *arg){
    (void)arg;iw_role=3;IwDiag *d=&iw_diag[3];d->tid=GetCurrentThreadId();depth_set(1);
    write_armed=iw_kind==4;write_expected=iw_kind==4?(_Atomic uint64_t *)((BYTE *)iw_first_address+8):NULL;
    __try {
        __try {
            __try {shared_write64(iw_first_address,123);d->returned++;}
            __except(capture_filter(GetExceptionInformation())) { /* Deliberately observed admission. */ }
        } __except(iw_probe_observer(GetExceptionInformation())) {d->propagated++;}
    } __finally {write_armed=0;write_expected=NULL;depth_set(0);}
    d->clear=depth_get()==0&&!write_armed&&!write_expected;return 0;
}
static void iw_join(HANDLE h){
    race_wait(h);DWORD code=99;if(!GetExitCodeThread(h,&code)||code)tls_abort();
}
static void iw_snapshot(void){
    Publisher *p=integrated_owner;Record *r=&p->s->records[0];
    printf("{\"event\":\"interleave\",\"phase\":%d,\"open\":%s,\"state\":%u,\"gate\":%u,\"published\":%llu,\"acked\":%llu,\"original\":%llu,\"errors\":%llu,\"phase_armed\":%ld,\"phase_depth\":%ld,\"stamp\":%llu,\"seq\":%llu,\"words\":[%llu,%llu,%llu,%llu],\"threads\":[",
        iw_phase,iw_open?"true":"false",atomic_load(&p->s->state),atomic_load(&p->gate),(unsigned long long)atomic_load(&p->s->published),
        (unsigned long long)atomic_load(&p->s->acked),(unsigned long long)atomic_load(&p->original_calls),(unsigned long long)atomic_load(&p->errors),
        iw_phase>=0&&iw_phase<3?iw_phase_armed[iw_phase]:-1,iw_phase>=0&&iw_phase<3?iw_phase_depth[iw_phase]:-1,
        (unsigned long long)atomic_load(&r->stamp),(unsigned long long)atomic_load(&r->seq),(unsigned long long)atomic_load(&r->word[0]),
        (unsigned long long)atomic_load(&r->word[1]),(unsigned long long)atomic_load(&r->word[2]),(unsigned long long)atomic_load(&r->word[3]));
    for(int i=1;i<4;i++){
        IwDiag *d=&iw_diag[i];
        printf("%s{\"role\":%d,\"tid\":%lu,\"code\":%lu,\"seen\":%ld,\"handled\":%ld,\"operation\":%ld,\"site\":%ld,\"offset\":%ld,\"armed\":%ld,\"match\":%ld,\"depth\":%ld,\"gate\":%ld,\"returned\":%ld,\"propagated\":%ld,\"clear\":%ld,\"writes\":%ld,\"acquired\":%ld}",
            i==1?"":",",i,d->tid,d->code,d->seen,d->handled,d->op,d->site,d->offset,d->armed,d->match,d->depth,d->gate,d->returned,d->propagated,d->clear,d->writes,d->acquired);
    }
    puts("]}");
}
static void iw_finish(void){
    if(!iw_open)return;
    race_signal(iw_second_go);for(int i=0;i<3;i++)race_signal(iw_go[i]);
    for(int i=0;i<2;i++)if(iw_threads[i]){iw_join(iw_threads[i]);CloseHandle(iw_threads[i]);iw_threads[i]=NULL;}
    HANDLE all[]={iw_ready,iw_prepared,iw_second_go,iw_hit[0],iw_hit[1],iw_hit[2],iw_go[0],iw_go[1],iw_go[2]};
    for(unsigned i=0;i<9;i++)if(!CloseHandle(all[i]))tls_abort();
    iw_open=0;iw_phase=3;
}
static int iw_command(const char *line){
    int kind,point;char mode[32];
    if(sscanf(line,"iw_start %d %d %31s",&kind,&point,mode)==3){
        if(iw_open||iw_diag[1].tid||kind<0||kind>4||point<0||point>6)tls_abort();
        iw_kind=kind;iw_mode=!strcmp(mode,"late_stop")?1:!strcmp(mode,"skip_recheck")?2:!strcmp(mode,"shared_arm")?3:0;
        late_stop=iw_mode==1;skip_recheck=iw_mode==2;iw_shared_arm=iw_mode==3;write_point=point;write_input=9;
        HANDLE *all[]={&iw_ready,&iw_prepared,&iw_second_go,&iw_hit[0],&iw_hit[1],&iw_hit[2],&iw_go[0],&iw_go[1],&iw_go[2]};
        for(unsigned i=0;i<9;i++){*all[i]=CreateEventW(NULL,TRUE,FALSE,NULL);if(!*all[i])tls_abort();}
        iw_open=1;iw_threads[0]=CreateThread(NULL,0,iw_worker,(void *)(uintptr_t)1,0,NULL);if(!iw_threads[0])tls_abort();race_wait(iw_ready);
        if(kind<3){iw_threads[1]=CreateThread(NULL,0,iw_worker,(void *)(uintptr_t)2,0,NULL);if(!iw_threads[1])tls_abort();}
        else race_signal(iw_prepared);
        race_wait(iw_hit[0]);iw_phase=0;iw_snapshot();return 1;
    }
    if(!iw_open)return 0;
    if(!strcmp(line,"iw_next\n")&&iw_phase<2){race_signal(iw_go[iw_phase]);iw_phase++;race_wait(iw_hit[iw_phase]);iw_snapshot();return 1;}
    if(!strcmp(line,"iw_second\n")&&iw_kind<3&&iw_phase==2){race_signal(iw_second_go);iw_join(iw_threads[1]);iw_snapshot();return 1;}
    if(!strcmp(line,"iw_probe\n")&&iw_kind>=3&&iw_phase==0&&!iw_threads[1]){
        iw_threads[1]=CreateThread(NULL,0,iw_probe_worker,NULL,0,NULL);if(!iw_threads[1])tls_abort();iw_join(iw_threads[1]);iw_snapshot();return 1;
    }
    if(!strcmp(line,"iw_finish\n")){iw_finish();iw_snapshot();return 1;}
    if(strcmp(line,"quit\n")){puts("{\"event\":\"error\",\"reason\":\"interleave_open\"}");return 1;}
    return 0;
}
