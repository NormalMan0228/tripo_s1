"""Ordered, transactional upgrades after all feature tables have been created."""

POLLING_INDEXES = (
    ('objects_owner_state_id', 'CREATE INDEX IF NOT EXISTS objects_owner_state_id ON objects(owner_id,state,id)'),
    ('mp_visits_host_expires', 'CREATE INDEX IF NOT EXISTS mp_visits_host_expires ON mp_visits(host_id,expires,user_id)'),
    ('mp_presence_host_scene_seen', 'CREATE INDEX IF NOT EXISTS mp_presence_host_scene_seen ON mp_presence(host_id,scene,seen)'),
)


def migrate_polling_indexes(db):
    """Upgrade existing worlds once; DDL and the marker commit or roll back together.

    Run after multiplayer/feature schema initialization, before serving requests.
    No table rebuilds, data rewrites or durability changes are needed.
    """
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM metadata WHERE key='migration:0118_polling_indexes'").fetchone():
            return
        for _, sql in POLLING_INDEXES:
            conn.execute(sql)
        conn.execute("INSERT INTO metadata(key,value) VALUES ('migration:0118_polling_indexes','1')")
