from cepearsiv.services.dashboard import dashboard_stats
from tests.conftest import make_user


def test_dashboard_stats_empty(db_session):
    user = make_user(db_session, username="dash0")
    stats = dashboard_stats(db_session, user.id)
    assert stats == {"total": 0, "last7": 0, "favorites": 0, "tags": 0}


def test_dashboard_stats_counts(db_session):
    from cepearsiv.schemas import ItemCreate
    from cepearsiv.services.items import create_item, toggle_flag

    user = make_user(db_session, username="dash1")
    for i in range(3):
        create_item(db_session, user.id, ItemCreate(type="note", title=f"not {i}"))
    item = create_item(db_session, user.id, ItemCreate(type="note", title="favori"))
    toggle_flag(db_session, user.id, item.id, flag="favorite")
    stats = dashboard_stats(db_session, user.id)
    assert stats["total"] == 4
    assert stats["favorites"] == 1
    assert stats["tags"] == 0


def test_dashboard_stats_excludes_deleted_and_other_users(db_session):
    from cepearsiv.schemas import ItemCreate
    from cepearsiv.services.items import create_item, toggle_flag

    user = make_user(db_session, username="dash2")
    other = make_user(db_session, username="dash3")
    create_item(db_session, user.id, ItemCreate(type="note", title="benim"))
    create_item(db_session, other.id, ItemCreate(type="note", title="baska"))
    item = create_item(db_session, user.id, ItemCreate(type="note", title="silecegim"))
    toggle_flag(db_session, user.id, item.id, flag="deleted")
    stats = dashboard_stats(db_session, user.id)
    assert stats["total"] == 1
