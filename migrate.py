import logging

from playhouse.migrate import *
from db import db, DBVersion
from varname import nameof

# logging.basicConfig(level=logging.INFO)

log = logging.getLogger("migrate")
current_version_db = DBVersion.select().count()

log.info(f"current_version_db={current_version_db}")

migrator = SqliteMigrator(db)


def migrate_non_stop(*operations):
    all_completed = True
    for ope in operations:
        try:
            ope.run()
        except Exception as e:
            all_completed = False
            log.warning(f"Propably already updated => Error {e}")

    return all_completed


def migrate1():
    if current_version_db > 0:
        log.info("Already applied, ignore")
        return

    # user_id = CharField()
    user_id = CharField(primary_key=False, null=True)
    pk_id1 = IntegerField()
    pk_id2 = AutoField()
    name = CharField(primary_key=False, unique=False)

    user_table_name = "user"
    try:
        log.info(f"We'll start migrating")

        with db.atomic():
            all_completed = migrate_non_stop(
                migrator.drop_index(user_table_name, f"{user_table_name}_name"),
                migrator.alter_column_type(user_table_name, nameof(name), name),
                migrator.alter_add_column(user_table_name, nameof(user_id), user_id),
                migrator.alter_add_column(user_table_name, "pk_id", pk_id1),
                migrator.alter_column_type(user_table_name, "pk_id", pk_id2),
            )
            if all_completed:
                log.info(f"Done migrate")
            else:
                log.info(f"Maybe already done that")
            try:
                DBVersion.create()
            except Exception as e:
                log.error(f"Some error try update DBVersion Table => Error {e}")
    except Exception as e:
        log.warning(f"Propably already updated => Error {e}")


def migrate2():
    if current_version_db > 1:
        log.info("Already applied, ignore")
        return

    locale = CharField(null=True)

    user_table_name = "user"

    try:
        log.info(f"We'll start migrating")

        with db.atomic():
            all_completed = migrate_non_stop(
                migrator.alter_add_column(user_table_name, nameof(locale), locale),
            )
            if all_completed:
                log.info(f"Done migrate")
                try:
                    DBVersion.create()
                except Exception as e:
                    log.error(f"Some error try update DBVersion Table => Error {e}")
            else:
                log.info(f"Maybe already done that")
    except Exception as e:
        log.warning(f"Propably already updated => Error {e}")


def start_migration():
    migrate1()
    migrate2()
