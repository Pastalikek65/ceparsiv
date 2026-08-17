import pytest

from cepearsiv.schemas import ItemCreate
from cepearsiv.services.dataport import export_user_data, import_user_data
from cepearsiv.services.items import create_item, list_items
from cepearsiv.services.tags import get_item_tags, set_item_tags
from tests.conftest import make_user


def _seed_items(db_session, user):
    i1 = create_item(
        db_session,
        user.id,
        ItemCreate(type="note", title="Not Bir", body="not govdesi"),
    )
    i2 = create_item(
        db_session,
        user.id,
        ItemCreate(type="bookmark", title="Yer İmi", url="https://example.com/a"),
    )
    i3 = create_item(
        db_session,
        user.id,
        ItemCreate(type="snippet", title="Kod", body="print(1)"),
    )
    set_item_tags(db_session, user.id, i1.id, ["python", "notlar"])
    set_item_tags(db_session, user.id, i2.id, ["python"])
    return [i1, i2, i3]


def _make_target_engine(tmp_path):
    from cepearsiv.db import get_engine, init_schema

    engine = get_engine(f"sqlite:///{tmp_path}/target.db")
    init_schema(engine)
    return engine


def test_export_import_roundtrip(db_engine, db_session, tmp_path):
    from sqlmodel import Session

    user = make_user(db_session, username="exporter")
    original = _seed_items(db_session, user)

    data = export_user_data(db_session, user.id)

    target_engine = _make_target_engine(tmp_path)
    try:
        with Session(target_engine) as target:
            new_user = make_user(target, username="imported")
            import_user_data(target, new_user.id, data)

            items, _ = list_items(target, new_user.id, page_size=50)
            assert len(items) == 3
            by_title = {i.title: i for i in items}
            assert by_title["Not Bir"].body == "not govdesi"
            assert by_title["Yer İmi"].url == "https://example.com/a"
            assert by_title["Kod"].type == "snippet"

            note = by_title["Not Bir"]
            note_tags = sorted(t.name for t in get_item_tags(target, new_user.id, note.id))
            assert note_tags == ["notlar", "python"]
            bm = by_title["Yer İmi"]
            assert [t.name for t in get_item_tags(target, new_user.id, bm.id)] == ["python"]
            for o in original:
                pass
    finally:
        target_engine.dispose()


def test_import_bad_json_rolls_back(db_session):
    from sqlmodel import select

    from cepearsiv.models import Item

    user = make_user(db_session, username="badimport")
    create_item(db_session, user.id, ItemCreate(type="note", title="Mevcut"))
    before = db_session.exec(select(Item).where(Item.user_id == user.id)).all()

    bad_data = {
        "schema_version": 1,
        "items": [
            {"type": "note", "title": "Geçerli", "body": "ok"},
            {"type": "note", "title": 12345, "body": None},
        ],
    }
    with pytest.raises(ValueError):
        import_user_data(db_session, user.id, bad_data)

    after = db_session.exec(select(Item).where(Item.user_id == user.id)).all()
    assert len(after) == len(before)
    assert {i.title for i in after} == {i.title for i in before}


def test_import_size_limit(db_session):
    user = make_user(db_session, username="sizeimport")
    big_body = "x" * 2200
    data = {
        "schema_version": 1,
        "items": [
            {"type": "note", "title": f"S{i}", "body": big_body} for i in range(5000)
        ],
    }
    with pytest.raises(ValueError):
        import_user_data(db_session, user.id, data)


def test_import_item_count_limit(db_session):
    user = make_user(db_session, username="countimport")
    data = {
        "schema_version": 1,
        "items": [{"type": "note", "title": f"K{i}", "body": "k"} for i in range(5001)],
    }
    with pytest.raises(ValueError):
        import_user_data(db_session, user.id, data)


def test_export_schema_version(db_session):
    user = make_user(db_session, username="schemauser")
    create_item(db_session, user.id, ItemCreate(type="note", title="Sürüm"))
    data = export_user_data(db_session, user.id)
    assert data["schema_version"] == 1
    assert data["exported_at"]
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1


def test_import_rebuilds_fts(db_engine, db_session):
    from sqlmodel import select

    from cepearsiv.models import Item
    from cepearsiv.services.search import search_items

    user = make_user(db_session, username="ftsimport")
    create_item(
        db_session,
        user.id,
        ItemCreate(type="note", title="Yeniden İnşa", body="benzersizindeks icerigi"),
    )
    data = export_user_data(db_session, user.id)

    for item in db_session.exec(select(Item).where(Item.user_id == user.id)).all():
        db_session.delete(item)
    db_session.commit()

    items, _ = search_items(db_session, user.id, q="benzersizindeks", backend="fts5")
    assert items == []

    import_user_data(db_session, user.id, data)

    items, _ = search_items(db_session, user.id, q="benzersizindeks", backend="fts5")
    assert len(items) == 1
    assert items[0].title == "Yeniden İnşa"
