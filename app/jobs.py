import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from . import export, model, source

ACTIVE=('downloading','geotiff','pdf')
class Cancelled(Exception): pass

class Jobs:
    def __init__(self,root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.stop=threading.Event(); self.thread=None
        with self.db() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, config TEXT NOT NULL, state TEXT, done INTEGER, total INTEGER, created REAL, updated REAL, started REAL, elapsed REAL DEFAULT 0, cancel INTEGER DEFAULT 0, error TEXT DEFAULT "")')
            c.execute('CREATE TABLE IF NOT EXISTS events (id TEXT, at REAL, state TEXT, done INTEGER, total INTEGER)')
            columns={r[1] for r in c.execute('PRAGMA table_info(jobs)')}
            if 'downloaded' not in columns:
                c.execute('ALTER TABLE jobs ADD COLUMN downloaded INTEGER DEFAULT 0')
            c.execute("UPDATE jobs SET state='interrupted', error='Serveren blev genstartet. Genoptag når du er klar.' WHERE state IN ('downloading','geotiff','pdf')")

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.root/'jobs.sqlite',timeout=20)
        try:
            c.row_factory=sqlite3.Row; c.execute('PRAGMA synchronous=FULL')
            with c:
                yield c
        finally:
            c.close()

    def list(self):
        with self.db() as c: rows=c.execute('SELECT * FROM jobs ORDER BY created DESC').fetchall()
        return [dict(r,config=json.loads(r['config'])) for r in rows]

    def get(self,id):
        if len(id)!=32 or any(c not in '0123456789abcdef' for c in id): raise KeyError(id)
        with self.db() as c: r=c.execute('SELECT * FROM jobs WHERE id=?',(id,)).fetchone()
        if r is None: raise KeyError(id)
        return dict(r,config=json.loads(r['config']))

    def create(self,raw):
        j=model.validate(raw); id=uuid.uuid4().hex; now=time.time()
        with self.db() as c:
            if c.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]>=10: raise ValueError('Køen har allerede 10 jobs.')
            c.execute('INSERT INTO jobs(id,config,state,done,total,created,updated) VALUES(?,?,?,?,?,?,?)',(id,json.dumps(j),'queued',0,0,now,now))
        return self.get(id)

    def action(self,id,action):
        self.get(id)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            state=c.execute('SELECT state FROM jobs WHERE id=?',(id,)).fetchone()[0]
            if action=='cancel':
                if state=='queued': c.execute("UPDATE jobs SET state='cancelled',updated=? WHERE id=?",(time.time(),id))
                elif state in ACTIVE: c.execute('UPDATE jobs SET cancel=1 WHERE id=?',(id,))
                else: raise ValueError('Jobbet kører ikke.')
            elif action=='resume':
                if state not in ('interrupted','cancelled','error'): raise ValueError('Jobbet kan ikke genoptages nu.')
                c.execute("UPDATE jobs SET state='queued',cancel=0,error='',updated=? WHERE id=?",(time.time(),id))
            elif action=='delete':
                if state in ACTIVE or state=='queued': raise ValueError('Annullér jobbet før sletning.')
                import shutil
                folder=self.root/id
                if folder.exists(): shutil.rmtree(folder)
                c.execute('DELETE FROM jobs WHERE id=?',(id,)); c.execute('DELETE FROM events WHERE id=?',(id,))

    def once(self,runner=export.run):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if r is None:return False
            c.execute("UPDATE jobs SET state='downloading',started=?,updated=? WHERE id=?",(time.time(),time.time(),r['id']))
        id=r['id']; start=time.monotonic(); previous=r['elapsed']
        def check():
            if self.stop.is_set() or self.get(id)['cancel']: raise Cancelled()
        def progress(state,done,total):
            check()
            with self.db() as c:
                c.execute('UPDATE jobs SET state=?,done=?,total=?,updated=?,elapsed=? WHERE id=?',
                          (state,done,total,time.time(),previous+time.monotonic()-start,id))
                if state=='downloading':
                    c.execute('UPDATE jobs SET downloaded=? WHERE id=?',(done,id))
                c.execute('INSERT INTO events VALUES(?,?,?,?,?)',(id,time.time(),state,done,total))
        try:
            runner(json.loads(r['config']),self.root/id,progress,check)
        except Exception as e:
            state='interrupted' if self.stop.is_set() else 'cancelled' if isinstance(e,Cancelled) else 'error'
            message=str(e) if isinstance(e,(source.SourceError,ValueError)) else 'Eksporten blev afbrudt. Genoptag eller kontrollér disk og kilde.'
            with self.db() as c: c.execute('UPDATE jobs SET state=?,error=?,updated=?,elapsed=? WHERE id=?',(state,message,time.time(),previous+time.monotonic()-start,id))
        return True

    def start(self):
        def loop():
            while not self.stop.is_set():
                if not self.once(): self.stop.wait(1)
        self.thread=threading.Thread(target=loop,daemon=True); self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread: self.thread.join(55)
