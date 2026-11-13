import { execFileSync } from 'node:child_process';

const PY_BRIDGE = `
import json, sqlite3, sys
req = json.loads(sys.stdin.read())
db = sqlite3.connect(req['db_path'])
db.row_factory = sqlite3.Row
op = req['op']
if op == 'exec':
    db.executescript(req['sql'])
    db.commit()
    print(json.dumps({'ok': True}))
elif op in ('run', 'get', 'all'):
    cur = db.execute(req['sql'], req.get('params', []))
    if op == 'run':
        db.commit()
        print(json.dumps({'changes': cur.rowcount, 'lastInsertRowid': cur.lastrowid}))
    elif op == 'get':
        row = cur.fetchone()
        print(json.dumps(dict(row) if row is not None else None))
    else:
        rows = cur.fetchall()
        print(json.dumps([dict(r) for r in rows]))
`;

function callSqlite(dbPath, op, sql, params = []) {
  const out = execFileSync('python3', ['-c', PY_BRIDGE], {
    input: JSON.stringify({ db_path: dbPath, op, sql, params }),
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });
  return JSON.parse(out);
}

export default class Database {
  constructor(dbPath) {
    this.dbPath = dbPath;
  }
  pragma(stmt) {
    callSqlite(this.dbPath, 'exec', `PRAGMA ${stmt};`);
  }
  exec(sql) {
    callSqlite(this.dbPath, 'exec', sql);
  }
  prepare(sql) {
    const dbPath = this.dbPath;
    return {
      run(...params) { return callSqlite(dbPath, 'run', sql, params); },
      get(...params) { return callSqlite(dbPath, 'get', sql, params); },
      all(...params) { return callSqlite(dbPath, 'all', sql, params); }
    };
  }
  transaction(fn) {
    return (...args) => fn(...args);
  }
}
