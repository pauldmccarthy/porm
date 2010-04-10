#!/bin/python
#
# porm - simple sqlite3 <-> python ORM layer
#
# This file provides very simple logic for conversion between rows of 
# a database table and lists of python objects. It supports lookup of
# simple types, and of basic one-to-many foreign key references.
#
# The following assumptions are made:
#
#   - All tables contain an 'id' field.
#   - Said id field is automatically generated by the database upon 
#     insertion.
#   - All valid id values are > 0.
#   - Foreign key fields reference the id field of the referenced table, 
#     and are named according to the following convention:
#
#       [table]_id
# 
#     where [table] is the name of the referenced table.
#   - Circular foreign key relationships do not exist.
#   - No table contains foreign key references to itself.
#
# Note: this module has no dependency upon sqlite3; it merely requires
#       objects which look and behave like the sqlite3.Connection and 
#       sqlite3.Cursor objects.
#
# Author: Paul McCarthy <pauld.mccarthy@gmail.com>
#

class Pormo:
  """
Base ORM object; all returned objects are of this type, and all objects 
passed to the save function are assumed to be of this type. If not, 
unexpected things may result.
  """
  pass

def query(db, table, where='', fkeylookup=True):
  """
Queries the given table in the given database according to the given where 
clause. Returns a list of objects representing the rows returned from the 
query.

db         - a handle to an open sqlite3 Connection object
table      - the name of the table to query
where      - the optional sql where clause
fkeylookup - optional, defaults to True; if false, foreign key lookups are
             not executed

As an example, to execute the given query:
  select * from people where age > 27

you would do this:
  oldies = porm.query(db, 'people', 'age > 27')
  """

  if len(where) is not 0: where = 'where %s' % where

  query = 'select * from %s %s' % (table, where)

  cursor = db.execute(query)
  return orm(db, table, cursor, fkeylookup)

def save(db, table, instance):
  """
Saves the given instance to the given table. If the instance already exists
it is updated; otherwise it is inserted.

db       - handle to an open sqlite3 Connection object
table    - name of the table to save the instance to
instance - the instance to save
  """

  # no id - assume this is a new instance
  if instance.id == 0: exists = False

  # id has been given - check to see if it is valid
  else:

    query  = 'select * from %s where id = %i' % (table, instance.id)
    exists = db.execute(query).fetchall()
    exists = len(exists) is not 0

  fields = [f for f in dir(instance) if f[0:2] != '__']
  values = [getattr(instance, f) for f in fields]

  # replace any foreign key objects with their ids
  for i in range(len(values)):
    if isinstance(values[i], Pormo):
      values[i] = values[i].id

  # update existing instance
  if exists:

    # wrapping all values with single quotes may not 
    # work with a non sqlite3 database; i'm not sure
    exprs = ','.join(['%s=\'%s\'' % e for e in zip(fields, values)])
    stmt  = 'update %s set %s where id=%i' % (table, exprs, instance.id)
    db.execute(stmt)

  # insert new instance
  else:

    fields = '%s' % ','.join(fields)
    values = '%s' % ','.join(values)

    stmt = 'insert into %s (%s) values (%s)' % (table, fields, values)
    db.execute(stmt)

  db.commit()

def orm(db, table, cursor, fkeylookup=True):
  """
Retrieves the rows from the given sqlite3 cursor and attempts to convert 
them into representative python objects. Any field which is a foreign key
to another table triggers a lookup; that field in the python object is set
to the subsequent python object returned from that lookup. A field is 
considered a foreign key if it is named as follows:

  [table]_id

The presence of a field named as such will trigger a lookup:
  select * from [table] where id = [field_value]

The subsequent field in the returned python objects will be set to the 
(first) result of this lookup for each row.

A table containing a reference to itself, or two (or more tables) with a 
circular foreign key relationship will cause infinite recursion.

db         - handle to an open sqlite3 Connection object
table      - name of the table in question
cursor     - handle to a valid sqlite3 Cursor object
fkeylookup - optional, defaults to True; if false, foreign key lookups are 
             not executed
  """
  
  objs     = []
  rows     = cursor.fetchall()
  rownames = [d[0] for d in cursor.description]

  for row in rows:

    obj = Pormo()
    for i in range(len(rownames)):

      name = rownames[i]
      val  = row[i]
      
      # foreign key lookup
      if fkeylookup and len(name) > 3 and name[-3:] == '_id':

        val  = query(db, name[:-3], 'id = %i' % val)

        if len(val) >= 1: setattr(obj, name, val[0])
        else:             setattr(obj, name, None)

      # simple type
      else:
        setattr(obj, name, val)

    objs.append(obj)

  return objs

