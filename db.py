from peewee import *
import datetime

db = SqliteDatabase('seeds_gratidaum_bot_database.db', pragmas=[('journal_mode', 'wal')])


class BaseModel(Model):
    class Meta:
        database = db


class DBVersion(BaseModel):
    number = AutoField()
    created_date = DateTimeField(default=datetime.datetime.now())


class User(BaseModel):
    pk_id = AutoField()
    user_id = CharField()
    name = CharField()
    username = CharField()
    locale = CharField()
    created_date = DateTimeField()
    updated_date = DateTimeField()


db.connect()
db.create_tables([User, DBVersion])
