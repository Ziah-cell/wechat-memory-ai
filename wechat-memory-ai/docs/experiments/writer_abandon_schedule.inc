/* Fault injection acts only on this known worker parked at our event barrier. */
static DWORD WINAPI dead_worker(void *arg){
    (void)arg;dead_role=1;scenario=NORMAL;
    __try {integrated_call(integrated_owner,PAYLOAD);dead_returned++;}
    __finally {dead_worker_finally++;}
    return 0;
}
static void dead_snapshot(void){
    HANDLE h=atomic_load(&dead_handle);DWORD w=WaitForSingleObject(h,0),code=0;
    int known=w==WAIT_OBJECT_0&&GetExitCodeThread(h,&code);Publisher *p=integrated_owner;Record *r=&p->s->records[0];
    printf("{\"event\":\"abandon\",\"wait\":%lu,\"exit_known\":%s,\"exit\":%lu,\"requested\":%s,\"state\":%u,\"gate\":%u,\"abandoned\":%s,\"published\":%llu,\"acked\":%llu,\"original\":%llu,\"returned\":%ld,\"publisher_finally\":%ld,\"hook_finally\":%ld,\"worker_finally\":%ld,\"paused_depth\":%u,\"paused_armed\":%d,\"stamp\":%llu,\"seq\":%llu,\"words\":[%llu,%llu,%llu,%llu]}\n",
        w,known?"true":"false",code,dead_requested?"true":"false",atomic_load(&p->s->state),atomic_load(&p->gate),atomic_load(&dead_abandoned)?"true":"false",
        (unsigned long long)atomic_load(&p->s->published),(unsigned long long)atomic_load(&p->s->acked),(unsigned long long)atomic_load(&p->original_calls),dead_returned,
        dead_publisher_finally,dead_hook_finally,dead_worker_finally,dead_paused_depth,dead_paused_armed,
        (unsigned long long)atomic_load(&r->stamp),(unsigned long long)atomic_load(&r->seq),(unsigned long long)atomic_load(&r->word[0]),
        (unsigned long long)atomic_load(&r->word[1]),(unsigned long long)atomic_load(&r->word[2]),(unsigned long long)atomic_load(&r->word[3]));
}
static void dead_join(void){if(WaitForSingleObject(atomic_load(&dead_handle),5000)!=WAIT_OBJECT_0)tls_abort();}
static void dead_finish(void){
    if(!dead_started)return;
    if(WaitForSingleObject(atomic_load(&dead_handle),0)==WAIT_TIMEOUT)race_signal(dead_resume);
    dead_join();
}
static void dead_close(void){
    if(!dead_started)return;
    /* Called only after service join: nobody else can wait on this handle. */
    HANDLE h=atomic_exchange(&dead_handle,NULL);DWORD code=0;if(!GetExitCodeThread(h,&code))tls_abort();
    printf("{\"event\":\"dead_cleanup\",\"thread_exit\":%lu,\"worker_finally\":%ld,\"claimed_cooperative\":%s}\n",code,dead_worker_finally,dead_mode==4||dead_worker_finally?"true":"false");
    if(!CloseHandle(h)||!CloseHandle(dead_ready)||!CloseHandle(dead_resume))tls_abort();
}
static int dead_command(const char *line){
    int stage;char mode[32];
    if(sscanf(line,"dead_start %d %31s",&stage,mode)==2){
        if(dead_started||stage<0||stage>10)tls_abort();dead_stage=stage;
        dead_mode=!strcmp(mode,"skip_abandon")?1:!strcmp(mode,"unlock_dead")?2:!strcmp(mode,"assume_dead")?3:!strcmp(mode,"false_cleanup")?4:0;
        write_point=stage>=8?3:-1;write_input=9;
        dead_ready=CreateEventW(NULL,TRUE,FALSE,NULL);dead_resume=CreateEventW(NULL,TRUE,FALSE,NULL);if(!dead_ready||!dead_resume)tls_abort();
        HANDLE h=CreateThread(NULL,0,dead_worker,NULL,CREATE_SUSPENDED,NULL);if(!h)tls_abort();
        atomic_store(&dead_handle,h);dead_started=1;if(ResumeThread(h)==(DWORD)-1)tls_abort();race_wait(dead_ready);dead_snapshot();return 1;
    }
    if(!dead_started)return 0;
    if(!strcmp(line,"dead_probe\n")){dead_snapshot();return 1;}
    if(!strcmp(line,"dead_kill\n")){
        HANDLE h=atomic_load(&dead_handle);
        if(WaitForSingleObject(h,0)!=WAIT_TIMEOUT||WaitForSingleObject(dead_ready,0)!=WAIT_OBJECT_0)tls_abort();
        if(!TerminateThread(h,73))tls_abort();dead_requested=1;dead_join();dead_snapshot();return 1;
    }
    if(!strcmp(line,"dead_release\n")){race_signal(dead_resume);dead_join();dead_snapshot();return 1;}
    return 0;
}
