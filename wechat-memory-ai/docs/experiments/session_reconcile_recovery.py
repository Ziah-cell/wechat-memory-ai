"""One recovery pass after receiver restart; never starts or controls a target.

The caller provides only the owned database path. Active identity/epoch comes
from the durable ledger. A deferred result does not claim recovery completed.
"""
import argparse,json,sqlite3
from session_reconcile_ledger import Ledger,Rejected

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--database',required=True);a=ap.parse_args()
 try:q=Ledger(a.database,require_existing=True)
 except Rejected as exc:
  print(json.dumps(dict(event='recovery',outcome='error',reason=str(exc))),flush=True);return 2
 except sqlite3.Error as exc:
  print(json.dumps(dict(event='recovery',outcome='error',reason='storage_error',sqlite_code=getattr(exc,'sqlite_errorcode',0))),flush=True);return 2
 try:
  snap=q.snapshot();epoch=snap['active']
  if epoch is None:result=dict(event='recovery',outcome='no_active_session')
  else:
   try:result=dict(event='recovery',outcome='ended',terminal=q.reconcile(epoch))
   except Rejected as exc:
    if str(exc) not in ('target_alive','binding_unknown'):raise
    result=dict(event='recovery',outcome='deferred',reason=str(exc),epoch=epoch)
   except sqlite3.Error as exc:
    code=getattr(exc,'sqlite_errorcode',0)
    if code&255 not in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED):raise
    result=dict(event='recovery',outcome='deferred',reason='busy',epoch=epoch)
  print(json.dumps(result),flush=True)
 finally:q.db.close()
 return 0
if __name__=='__main__':raise SystemExit(main())
