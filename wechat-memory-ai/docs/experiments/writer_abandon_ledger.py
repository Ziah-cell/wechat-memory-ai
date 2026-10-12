"""New fictional terminal-session protocol; no product or real application I/O.

The trusted fixture relay supplies epoch and copied records. Native target
binding is liveness evidence, not authentication of arbitrary record senders.
"""
import argparse,json,sqlite3,sys
from pathlib import Path
from target_lifetime_ledger import Rejected,batch_value,epoch_value
from session_target_binding import identity,probe

R=Path(__file__).resolve().parents[2];C=R/'data/writer-abandon-20261012'

class Ledger:
 def __init__(self,path,mode='exact',require_existing=False):
  path=Path(path).resolve()
  if not path.is_relative_to(C.resolve()) or path.name!='ledger.sqlite3':raise Rejected('fixture_path_only')
  if sqlite3.sqlite_version_info<(3,51,3):raise Rejected('sqlite_version')
  if require_existing and not path.is_file():raise Rejected('missing_database')
  self.mode=mode;self.limited=False;fresh=not path.exists()
  # mode=rw also prevents creation if the file disappears after the path check.
  self.db=sqlite3.connect(path.as_uri()+'?mode=rw' if require_existing else path,
                         uri=require_existing,timeout=0,isolation_level=None);self.db.row_factory=sqlite3.Row
  try:
   self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA synchronous=FULL')
   if fresh:
    self.db.execute('PRAGMA journal_mode=WAL')
    self.db.executescript('''BEGIN IMMEDIATE;
     CREATE TABLE fixture_padding(data BLOB);
     CREATE TABLE operations(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,epoch TEXT NOT NULL);
     CREATE TABLE sessions(epoch TEXT PRIMARY KEY,state TEXT NOT NULL,last_seq INTEGER NOT NULL,
       observed_hi INTEGER NOT NULL,target_pid INTEGER NOT NULL,target_created INTEGER NOT NULL,
       end_op INTEGER REFERENCES operations(id));
     CREATE TABLE control(id INTEGER PRIMARY KEY CHECK(id=1),epoch TEXT REFERENCES sessions(epoch));
     INSERT INTO control VALUES(1,NULL);
     CREATE TABLE inbox(epoch TEXT REFERENCES sessions(epoch),seq INTEGER NOT NULL,payload TEXT NOT NULL,
       commit_op INTEGER NOT NULL REFERENCES operations(id),PRIMARY KEY(epoch,seq));
     CREATE TABLE endings(epoch TEXT PRIMARY KEY REFERENCES sessions(epoch),
       end_op INTEGER NOT NULL UNIQUE REFERENCES operations(id),detail TEXT NOT NULL);
     PRAGMA user_version=2;COMMIT;''')
   if self.db.execute('PRAGMA user_version').fetchone()[0]!=2:raise Rejected('schema')
   if self.db.execute('PRAGMA journal_mode').fetchone()[0]!='wal':raise Rejected('journal_mode')
  except BaseException:self.db.close();raise

 def transaction(self,work,checkpoint=None):
  self.db.execute('BEGIN IMMEDIATE')
  try:
   result=work()
   if checkpoint:checkpoint('before_commit')
   self.db.execute('COMMIT')
  except BaseException:
   if self.db.in_transaction:self.db.execute('ROLLBACK')
   raise
  if checkpoint:checkpoint('after_commit')
  return result

 def operation(self,kind,epoch):return self.db.execute('INSERT INTO operations(kind,epoch) VALUES(?,?)',(kind,epoch)).lastrowid
 def session(self,epoch):
  r=self.db.execute('SELECT * FROM sessions WHERE epoch=?',(epoch,)).fetchone()
  if r is None:raise Rejected('unknown_epoch')
  return r
 def live(self,r):
  p=probe(r['target_pid'],r['target_created'])
  if p['state']=='unknown':raise Rejected('binding_unknown')
  if p['state']!='live':raise Rejected('target_dead')
 def active(self,epoch):
  r=self.session(epoch)
  if r['state']!='active' or self.db.execute('SELECT epoch FROM control').fetchone()[0]!=epoch:raise Rejected('closed')
  self.live(r);return r

 def begin(self,epoch,target):
  epoch_value(epoch);pid,created=identity(target)
  def work():
   if self.db.execute('SELECT 1 FROM sessions WHERE epoch=?',(epoch,)).fetchone():raise Rejected('epoch_used')
   if self.db.execute('SELECT epoch FROM control').fetchone()[0] is not None:raise Rejected('active_epoch')
   p=probe(pid,created)
   if p['state']=='replaced':raise Rejected('binding_mismatch')
   if p['state']=='unknown':raise Rejected('binding_unknown')
   if p['state']!='live':raise Rejected('target_dead')
   self.db.execute('INSERT INTO sessions VALUES(?,"active",0,0,?,?,NULL)',(epoch,pid,created))
   self.db.execute('UPDATE control SET epoch=?',(epoch,));op=self.operation('begin',epoch)
   return dict(epoch=epoch,begin_op=op,target=target)
  return self.transaction(work)

 def observe(self,epoch,records):
  epoch_value(epoch);batch=batch_value(records)
  def work():
   r=self.active(epoch);hi=max(r['observed_hi'],batch[-1][0]);op=self.operation('observe',epoch)
   self.db.execute('UPDATE sessions SET observed_hi=? WHERE epoch=?',(hi,epoch))
   return dict(observed_hi=hi,observe_op=op)
  return self.transaction(work)

 def accept(self,epoch,records,checkpoint=None):
  epoch_value(epoch);batch=batch_value(records)
  def work():
   # Negative control deliberately allows a terminal epoch to insert late rows.
   r=self.session(epoch) if self.mode=='accept_terminal' else self.active(epoch)
   if self.limited:self.db.execute('INSERT INTO fixture_padding VALUES(zeroblob(1048576))')
   last=r['last_seq'];added=duplicates=0;op=None
   for seq,payload in batch:
    old=self.db.execute('SELECT payload FROM inbox WHERE epoch=? AND seq=?',(epoch,seq)).fetchone()
    if old:
     if old[0]!=payload:raise Rejected('conflict')
     duplicates+=1;continue
    if seq!=last+1:raise Rejected('gap')
    if op is None:op=self.operation('accept',epoch)
    self.db.execute('INSERT INTO inbox VALUES(?,?,?,?)',(epoch,seq,payload,op));added+=1;last=seq
   self.db.execute('UPDATE sessions SET last_seq=?,observed_hi=max(observed_hi,?) WHERE epoch=?',(last,last,epoch))
   return dict(added=added,duplicates=duplicates,last_seq=last,commit_op=op)
  r=self.transaction(work,checkpoint);seq=batch[-1][0]
  r['ack']=dict(epoch=epoch,seq=seq,generation=(seq-1)//8+1)
  return r

 def reconcile(self,epoch,checkpoint=None):
  epoch_value(epoch)
  def work():
   r=self.session(epoch)
   if r['state']=='ended':return json.loads(self.db.execute('SELECT detail FROM endings WHERE epoch=?',(epoch,)).fetchone()[0])
   p=probe(r['target_pid'],r['target_created'])
   if self.mode=='probe_unknown':p=dict(state='unknown',reason='injected_query_failure')
   if self.mode=='assume_dead':p=dict(state='dead',reason='incorrect_assumption')
   if p['state']=='live':raise Rejected('target_alive')
   if p['state']=='unknown':raise Rejected('binding_unknown')
   if self.limited:self.db.execute('INSERT INTO fixture_padding VALUES(zeroblob(1048576))')
   op=self.operation('end',epoch);missing=r['observed_hi']-r['last_seq']
   detail=dict(epoch=epoch,state='ended',end_op=op,kind='source_ended_unknown_tail',
     committed_last_seq=r['last_seq'],observed_hi=r['observed_hi'],discarded_observed=missing,
     discarded_from=r['last_seq']+1 if missing else None,discarded_to=r['observed_hi'] if missing else None,
     tail_unknown=self.mode!='zero_tail',target=dict(pid=r['target_pid'],created=r['target_created']),proof=p)
   self.db.execute('INSERT INTO endings VALUES(?,?,?)',(epoch,op,json.dumps(detail,sort_keys=True)))
   self.db.execute('UPDATE sessions SET state="ended",end_op=? WHERE epoch=?',(op,epoch))
   self.db.execute('UPDATE control SET epoch=NULL WHERE epoch=?',(epoch,))
   return detail
  return self.transaction(work,checkpoint)

 def replay(self,epoch,records):
  epoch_value(epoch);batch=batch_value(records)
  self.db.execute('BEGIN')
  try:
   r=self.session(epoch)
   if r['state']!='ended':raise Rejected('not_ended')
   for seq,payload in batch:
    old=self.db.execute('SELECT payload FROM inbox WHERE epoch=? AND seq=?',(epoch,seq)).fetchone()
    if old is None:raise Rejected('not_committed')
    if old[0]!=payload and self.mode!='skip_replay_match':raise Rejected('conflict')
   return dict(duplicates=len(batch),read_only=True,ack=None,end_op=r['end_op'])
  finally:self.db.execute('ROLLBACK')

 def snapshot(self):
  self.db.execute('BEGIN')
  try:
   d={n:[dict(x) for x in self.db.execute('SELECT * FROM '+n+' ORDER BY '+('id' if n=='operations' else 'epoch'))] for n in ['sessions','operations','endings','inbox']}
   for row in d['inbox']:row['payload']=json.loads(row['payload'])
   for row in d['endings']:row['detail']=json.loads(row['detail'])
   return dict(**d,active=self.db.execute('SELECT epoch FROM control').fetchone()[0],integrity=self.db.execute('PRAGMA integrity_check').fetchone()[0])
  finally:self.db.execute('ROLLBACK')

def emit(value):print(json.dumps(value,separators=(',',':')),flush=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--database',required=True);ap.add_argument('--mode',default='exact',choices=['exact','assume_dead','accept_terminal','zero_tail','skip_replay_match','probe_unknown']);a=ap.parse_args()
 try:q=Ledger(a.database,a.mode)
 except (Rejected,sqlite3.Error) as exc:emit(dict(event='error',reason=str(exc)));return 1
 emit(dict(event='ready',synchronous=q.db.execute('PRAGMA synchronous').fetchone()[0],sqlite=sqlite3.sqlite_version,schema=2))
 try:
  for line in sys.stdin:
   if line.strip()=='quit':break
   try:
    req=json.loads(line)
    if not isinstance(req,dict):raise Rejected('protocol')
    point=req.get('checkpoint')
    if point not in (None,'before_commit','after_commit'):raise Rejected('checkpoint')
    def checkpoint(stage):
     if stage==point:
      emit(dict(event='checkpoint',stage=stage))
      if sys.stdin.readline().strip()!='resume':raise Rejected('checkpoint_cancelled')
    op=req['op']
    if op=='begin':r=q.begin(req['epoch'],req['target'])
    elif op=='observe':r=q.observe(req['epoch'],req['records'])
    elif op=='accept':r=q.accept(req['epoch'],req['records'],checkpoint)
    elif op=='reconcile':r=q.reconcile(req['epoch'],checkpoint)
    elif op=='replay':r=q.replay(req['epoch'],req['records'])
    elif op=='snapshot':r=q.snapshot()
    elif op=='limit_pages':
     n=q.db.execute('PRAGMA page_count').fetchone()[0];q.db.execute(f'PRAGMA max_page_count={n}');q.limited=True;r=dict(pages=n)
    elif op=='unlimit_pages':q.db.execute('PRAGMA max_page_count=1073741823');q.limited=False;r={}
    else:raise Rejected('operation')
    emit(dict(event='result',ok=True,**r))
   except Rejected as exc:emit(dict(event='result',ok=False,reason=str(exc)))
   except sqlite3.Error as exc:
    code=getattr(exc,'sqlite_errorcode',0);emit(dict(event='result',ok=False,reason='busy' if code&255 in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED) else 'storage_error',sqlite_code=code))
   except (KeyError,TypeError,ValueError):emit(dict(event='result',ok=False,reason='protocol'))
 finally:q.db.close()
 emit(dict(event='bye'));return 0
if __name__=='__main__':raise SystemExit(main())
