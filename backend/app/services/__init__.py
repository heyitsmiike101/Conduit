"""
Services package.

Important: SQLAlchemy assigns UUID primary keys at INSERT time (flush/commit),
not at object instantiation. Always call db.flush() before using a new object's
ID as a foreign key in another object.

  script = Script(...)
  db.add(script)
  db.flush()           # ← script.id is now populated
  db.add(ScriptPermission(script_id=script.id, ...))
  db.commit()
"""
