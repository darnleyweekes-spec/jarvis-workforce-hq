"""Local, cited document search fallback. No hosted database or model."""
import sqlite3
from alpha_runtime import MissionError

def search_documents(task,documents,query,limit=5):
    if 'knowledge.local.read' not in task.allowed_tools: raise MissionError('Missing knowledge.local.read')
    if not isinstance(query,str) or not 1<=len(query)<=500 or not 1<=limit<=20: raise ValueError('Invalid search bounds')
    if len(documents)>100 or any(len(d['text'])>100000 for d in documents): raise ValueError('Document limit exceeded')
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE VIRTUAL TABLE docs USING fts5(source UNINDEXED, body)')
        db.executemany('INSERT INTO docs VALUES (?,?)',[(d['source'],d['text']) for d in documents])
        # Treat input as literal terms, never as an arbitrary FTS expression.
        terms=['"'+word.replace('"','""')+'"' for word in query.split()]
        if not terms: raise ValueError('Empty search')
        rows=db.execute('SELECT source,snippet(docs,1,\'\',\'\',\' … \',48) FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?',(' OR '.join(terms),limit)).fetchall()
    return [{'source':source,'excerpt':excerpt,'verification':'observed document text'} for source,excerpt in rows]
