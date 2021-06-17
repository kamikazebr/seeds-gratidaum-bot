from peewee import *
import datetime

db = SqliteDatabase('seeds_gratidaum_bot_database.db', pragmas=[('journal_mode', 'wal')])


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    name = CharField(unique=True, primary_key=True)
    username = CharField()
    created_date = DateTimeField()
    updated_date = DateTimeField()


db.connect(reuse_if_open=True)
db.create_tables([User])