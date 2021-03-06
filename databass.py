'''Databass is a interface meant to simplify database transactions in Python
by letting you use dictionaries and list of dictionaries for your transactions
instead of writing pure SQL-code. Thus easily letting you generate and read
JSON-feeds. Preferably over HTTPS.

The syntax for doing operations and generating feeds is identical. And the
result from reading the feed is identical to as if the operation were done
locally.

(Only tested with Python 3. (Automatic JOIN with dictionaries is on the TODO
list. But you can still write your own SQL and get the list of dictionaries
from joined SELECTS.))

NAME

Databass is a punmanteau from "data" and "bass" because bass sound like base.
And you can feed the bass. Bass feed is much funnier than Atom feed.

Copyright (C) 2018 Lord Wolfenstein

https://github.com/LordWolfenstein/databass

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
import mysql.connector as MariaDB
from tabulate import tabulate
from typing import Union
import json

class databass:
    '''Class that simplifies database connections.'''
    __version__ = 0.5

    def __init__(self, config: dict, verbose: bool=False):
        '''Config format:
        config = {'user'     : 'root',
                  'password' : 'pass',
                  'host'     : '1.2.3.4',
                  'port'     : '3306',
                  'database' : 'test'}'''
        self._bass = MariaDB.connect(**config)
        self.verbose=verbose
        #self._cursor  = self._bass.cursor(dictionary=True)

        # Feed eating functions
        self._feedeaters={}
        self._feedeaters["create"]      = self.EatCreate
        self._feedeaters["alter table"] = self.EatAlterTable
        self._feedeaters["drop"]        = self.EatDrop
        self._feedeaters["insert"]      = self.EatInsert
        self._feedeaters["update"]      = self.EatUpdate
        self._feedeaters["delete"]      = self.EatDelete
        self._feedeaters["insupd"]      = self.EatInsupd

    def run(self, sql: str, *args: Union[tuple, str]) -> Union[list, bool, str]:
        '''Runs a query.
           Returns a list of dictionaries on successfull SELECT.
        '''
        # TODO: add **kwargs
        cursor = self._bass.cursor(dictionary=True)
        if self.verbose:
            print("sql  =", sql)
            print("args =", args)
        try:
            if len(args)>0:
                if type(args[0])==tuple:
                    cursor.execute(sql, *args) # at db.run(sql, ("219154664", "CPU0_PVCCIO")) I think...
                if type(args[0])==str:
                    cursor.execute(sql, args) # at db.run(sql, "219154664", "CPU0_PVCCIO") I hope...
            else:
                cursor.execute(sql)
        except MariaDB.Error as err:
            cursor.close()
            return "Database Error: " + str(err)
        if cursor.description:
            ret=cursor.fetchall()
            self._bass.commit()
            cursor.close()
            return ret
        else:
            self._bass.commit()
            cursor.close()
            return True

    def count(self, table: str) -> Union[str, bool]:
        '''Returns the number of rows in a given table.'''
        if table not in self.tables():
            return False
        return self.run("SELECT count(*) FROM `{}`".format(table))[0]["count(*)"]

    def name(self) -> str:
        '''Returns the name of the currently selected database.'''
        return self.run("SELECT DATABASE()")[0]["DATABASE()"]

    def tables(self) -> list:
        '''Returns a list of tables in the database.'''
        result = self.run("SHOW tables")
        tables = []
        name = self.name()
        for table in result:
            tables.append(table["Tables_in_" + name])
        return tables

    def colums(self, table: str) -> Union[list, bool]:
        '''Returns all the column in the table'''
        if table not in self.tables():
            return False
        ret = []
        columns = self.run("SHOW COLUMNS FROM `{}`".format(table))
        for c in columns:
            ret.append(c["Field"])
        return ret

    def info(self, table: str) -> Union[str, bool]:
        '''Returns detailed table info in dictionary form'''
        if table not in self.tables():
            return False
        return self.run("DESCRIBE `{}`".format(table))

    def code(self, table: str) -> Union[str, bool]:
        '''Returns the code used to create the table'''
        if table not in self.tables():
            return False
        return self.run("SHOW CREATE TABLE `{}`".format(table))[0]["Create Table"]

    def drop(self, table: str) -> Union[bool, str]:
        '''Drops the table'''
        if table not in self.tables():
            return False
        return self.run("DROP TABLE `{}`".format(table))

    def create(self, tableconfigs: dict) -> list:
        '''Creates a table according to the given configuration.
        This used the same syntax that MariaDB used when you DESCRIBE a table
        tableconfigs is a dictionary of the format
        tableconfigs = {
            "tablename1" :
            [
                {
                    "Field": "id",
                    "Type": "int(11)",
                    "Null": "NO",
                    "Key": "PRI",
                    "Default": "None",
                    "Extra": "auto_increment"
                },
                {
                    "Field": "text",
                    "Type": "text",
                    "Null": "YES",
                    "Key": "",
                    "Default": "'Nothing!'",
                    "Extra": ""
                }
            ],
            "tablename2" :
            [
                {
                    "Field": "id",
                    "Type": "int(11)",
                    "Null": "NO",
                    "Key": "PRI",
                    "Default": "None",
                    "Extra": "auto_increment"
                },
                {
                    "Field": "time",
                    "Type": "double",
                    "Null": "YES",
                    "Key": "",
                    "Default": "None",
                    "Extra": ""
                }
            ]
        }
        '''
        ret = []
        for t in tableconfigs:
            # print(tableconfigs[t])
            sql = "CREATE TABLE `{}` (".format(t)
            for column in tableconfigs[t]:
                sql += "`{}` {} {} {} {}, ".format(column["Field"],
                column["Type"],
                ("NOT NULL" if column["Null"]=="NO" else "") if "NULL" in column else "",
                ("DEFAULT({})".format(column["Default"]) if column["Default"]!="None" else "") if "Default" in column else "",
                column["Extra"] if "Extra" in column else "")
            keys = "PRIMARY KEY("
            for column in tableconfigs[t]:
                if "Key" in column:
                    if column["Key"]=="PRI":
                        keys += column["Field"] + ", "
            if keys.endswith(", "):
                keys = keys[:-2]
            keys = keys + ") )"
            if keys != "PRIMARY KEY() )":
                sql += keys
            if sql.endswith(", "):
                sql = sql[:-2]+")"
            # print("sql =", sql)
            ret.append(self.run(sql))
        return ret

    def insupd(self, table: str, data: Union[dict, list]) -> Union[list, str]:
        '''Inserts if not existing, updates on existing'''
        if type(data)==list:
            return [self.insupd(table, d) for d in data]
        else:
            if table not in self.tables():
                return "Error, table {} not in database".format(table)
            tableColums = self.colums(table)
            for column in data.keys():
                if column not in tableColums:
                    return "Error, column {} not in table {}".format(column, table)

            sql = "INSERT INTO `{}` (".format(table)
            for d in data:
                sql += "`{}`, ".format(d)
            sql = sql[:-2] + ") VALUES("
            for d in data:
                if type(data[d])==str:
                    sql += "'{}', ".format(data[d].replace("'", "''"))
                elif d==None:
                    sql += "null, "
                else:
                    sql += "{}, ".format(data[d])
            sql = sql[:-2] + ") ON DUPLICATE KEY UPDATE "
            for d in data:
                if type(data[d])==str:
                    sql += "`{}`='{}', ".format(d, data[d].replace("'", "''"))
                elif d==None:
                    sql += "`{}`=null, ".format(d)
                else:
                    sql += "`{}`={}, ".format(d, data[d])
            sql = sql[:-2]
            return self.run(sql)

    def insert(self, table: str, data: Union[dict, list]) -> Union[bool, str]:
        '''Inserts data in to the table.
        data: a dictionary or a list of dictionaries with keywords equal to column names.
        '''
        if table not in self.tables():
            return False
        if type(data)==dict:
            data = [data]
        tableColums = self.colums(table)
        for d in data:
            for column in d.keys():
                if column not in tableColums:
                    return False

        sql = "INSERT INTO `{}` (".format(table)
        for d in data[0]:
            sql += "`{}`, ".format(d)
        sql = sql[:-2] + ") VALUES "
        for l in data:
            sql+= "("
            for d in l:
                if type(l[d])==str:
                    sql += "'{}', ".format(l[d].replace("'", "''"))
                elif d==None:
                    sql += "null, "
                else:
                    sql += "{}, ".format(l[d])
            sql = sql[:-2] + "), "
        sql = sql[:-2]
        return self.run(sql)

    def select(self, table: str, where: dict={}, wherenot: dict={}, columns: list=["*"]) -> Union[list, str, bool]:
        '''Selects rows from the given table where the contritions in condition is met.
        Currently only is equal and not equal conditions work. Making less than and
        grater than still requires handwritten SQL-code.

        By default gets all columns. Since you are working with dictionaries just pick
        what you need and ignore the rest. We are trying to be as Pythonic as possible
        here. That is why the columns last. You can ignore them.
        '''
        if table not in self.tables():
            return False
        tableColums = self.colums(table)
        for column in where.keys():
            if column not in tableColums:
                return False
        for column in wherenot.keys():
            if column not in tableColums:
                return False
        if columns != ["*"]:
            for column in columns:
                if column not in tableColums:
                    return False

        sql = "SELECT {} FROM `{}`".format(", ".join(columns), table)
        if where!={} or wherenot!={}:
            sql += " WHERE"
        if where!={}:
            for w in where:
                sql += " `{}`='{}' AND".format(w, where[w].replace("'", "''"))
            sql = sql[:-4]
        if wherenot!={}:
            for w in wherenot:
                sql += " `{}`!='{}' AND".format(w, wherenot[w].replace("'", "''"))
            sql = sql[:-4]
        return self.run(sql)

    def update(self, table: str, data: dict, where: dict={}, wherenot: dict={}) -> Union[str, bool]:
        '''Updates an existing post in the database
        At least one of where and wherenot is required.'''
        if table not in self.tables():
            return False
        tableColums = self.colums(table)
        for column in where.keys():
            if column not in tableColums:
                return False
        for column in wherenot.keys():
            if column not in tableColums:
                return False
        for column in data.keys():
            if column not in tableColums:
                return False

        sql = "UPDATE {} SET ".format(table)
        for d in data:
            sql += "`{}`='{}', ".format(d, data[d].replace("'", "''"))
        sql = sql[:-2]
        sql += " WHERE"
        if where!={}:
            for w in where:
                sql += " `{}`='{}' AND".format(w, where[w].replace("'", "''"))
            sql = sql[:-4]
        if wherenot!={}:
            for w in wherenot:
                sql += " `{}`!='{}' AND".format(w, wherenot[w].replace("'", "''"))
            sql = sql[:-4]
        return self.run(sql)

    def delete(self, table: str, where: dict={}, wherenot: dict={}) -> Union[str, bool]:
        '''Deletes rows form the table where the conditions is met.'''
        if table not in self.tables():
            return False
        tableColums = self.colums(table)
        for column in where.keys():
            if column not in tableColums:
                return False
        for column in wherenot.keys():
            if column not in tableColums:
                return False
        sql = "DELETE FROM `{}` WHERE".format(table)
        if where!={}:
            for w in where:
                sql += " `{}`='{}' AND".format(w, where[w].replace("'", "''"))
            sql = sql[:-4]
        if wherenot!={}:
            for w in wherenot:
                sql += " `{}`!='{}' AND".format(w, wherenot[w].replace("'", "''"))
            sql = sql[:-4]
        return self.run(sql)

    def AlterTable(self, table: str, add: Union[list, dict]=[], drop: Union[list, str]=[]) -> Union[str, bool]:
        '''Alters a table'''
        if table not in self.tables():
            return False

        sql = "ALTER TABLE `{}`".format(table)
        if type(drop)==str:
            drop = [drop]
        if drop!=[]:
            for c in drop:
                sql += " DROP COLUMN `{}`, ".format(c)
        if add==[]:
            sql = sql[:-2]
        if type(add)==dict:
            add = [add]
        if add!=[]:
            for a in add:
                sql += " ADD COLUMN IF NOT EXISTS "
                sql += "`{}` {} {} {} {}, ".format(a["Field"],
                a["Type"],
                ("NOT NULL" if a["Null"]=="NO" else "") if "NULL" in a else "",
                ("DEFAULT({})".format(a["Default"]) if a["Default"]!="None" else "") if "Default" in a else "",
                a["Extra"] if "Extra" in a else "")
            sql = sql [:-2]
        return self.run(sql)

    def clear(self, table: str) -> Union[str, bool]:
        '''Clears/truncates all rows in a table'''
        if table not in self.tables():
            return "Error, no such table"
        return self.run("TRUNCATE TABLE " + table)

    '''Feed generators'''
    def FeedCreate(self, tableconfigs: dict) -> dict:
        '''Returns a feed for the create operation to be read by EatFeed() on another server.

        The feeds need to be put in a list afterwards.'''
        return {"operation":"create", "tableconfigs":tableconfigs}

    def FeedAlterTable(self, table: str, add: list=[], drop: Union[list, str]=[]) -> dict:
        '''Returns a feed for the alter operation to be read by EatFeed() on another server.

        The feeds need to be put in a list afterwards.'''
        return {"operation":"alter table", "table":table, "add":add, "drop":drop}

    def FeedDrop(self, table: str) -> dict:
        '''Returns a feed for the drop operation to be read by EatFeed() on another server.

        The feeds need to be put in a list afterwards.'''
        return {"operation":"drop", "table":table}

    def FeedInsert(self, table: str, data: dict) -> dict:
        '''Returns a feed for the insert operation to be read by EatFeed() on another server.

        The feeds need to be put in a list afterwards.'''
        return {"operation":"insert", "table":table, "data":data}

    def FeedUpdate(self, table: str, data: dict, where: dict={}, wherenot: dict={}) -> dict:
        '''Returns a feed for the update operation to be read by EatFeed() on another server.

        The feeds need to be put in a list afterwards.'''
        return {"operation":"update", "table":table, "data":data, "where":where, "wherenot":wherenot }

    def FeedInsupd(self, table: str, data: Union[list, dict]) -> dict:
        '''Returns a feed for the insert/update operation to be read by EatFeed() on another server.

        The feeds need to be put in a list afterwards.'''
        return {"operation":"insupd", "table":table, "data":data}

    def FeedDelete(self, table: str, where: dict={}, wherenot: dict={}) -> dict:
        '''Returns a feed for the delete operation to be read by EatFeed() on another server.

        The feeds need to be put in a list afterwards.'''
        return {"operation":"delete", "table": table, "where" : where, "wherenot" : wherenot }

    def GenerateFeed(self, feed: list) -> str:
        '''Generated a json string from the list of feeds in feed.
        This is the thing you are supposed to put in the feed for databass
        to eat on the other side. It contains the keyword "bassfeed".
        Other then that you can add whatever server information you like
        to the json before you put it in the actual feed.'''
        return json.dumps({"bassfeed":feed})

    '''Feed readers, because a feed is bass food in this case'''
    def EatCreate(self, feed: dict):
        return self.create(feed["tableconfigs"])

    def EatAlterTable(self, feed: dict) -> Union[str, bool]:
        table = feed["table"]
        add   = feed["add"]
        drop  = feed["drop"]
        return self.AlterTable(table, add, drop)

    def EatDrop(self, feed: dict) -> Union[bool, str]:
        return self.drop(feed["table"])

    def EatInsert(self, feed: dict) -> Union[bool, str]:
        table = feed["table"]
        data  = feed["data"]
        return self.insert(table, data)

    def EatUpdate(self, feed: dict) -> Union[str, bool]:
        table    = feed["table"]
        data     = feed["data"]
        where    = feed["where"]
        wherenot = feed["wherenot"]
        return self.update(table, data, where, wherenot)

    def EatInsupd(self, feed: dict) -> Union[list, str]:
        table    = feed["table"]
        data     = feed["data"]
        return self.insupd(table, data)

    def EatDelete(self, feed: dict) -> Union[str, bool]:
        table    = feed["table"]
        where    = feed["where"]
        wherenot = feed["wherenot"]
        return self.delete(table, where, wherenot)

    def EatFeed(self, feed: str) -> str:
        '''This functions reads a feed, handles it and does operations
        to the database.

        feed: a json string with atleast the keyword "bassfeed" in it.
        '''
        feeds = json.loads(feed)
        ret = ""
        for f in feeds["bassfeed"]:
            ret += str(self._feedeaters[f["operation"]](f)) + " "
        return ret

def shorten(data: list, maxlen: int=50) -> list:
    '''Shortens the contents of a list of dictionaries to make it
    more eye friendly when printed with tabulate.
    data: A list of dictionaries
    '''
    ret=[]
    for i in data:
        r={}
        for j in i:
            r[j]=unicode(i[j])[:maxlen].replace("\n", " ")
        ret.append(r)
    return ret

def printrows(rows: list, format: str = "fancy_grid") -> None:
    '''Pretty prints the list of dictionaries returned by databass.run()
    data: A list of dictionaries
    '''
    if type(rows)==list:
        if len(rows) > 0:
            print(tabulate([i.values() for i in rows], rows[0].keys(), format))
        else:
            print(rows)
    else:
        print(rows)

