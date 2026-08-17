import pytest

from cepearsiv.schemas import ItemCreate
from cepearsiv.services.items import create_item, list_items, toggle_flag
from cepearsiv.services.tags import (
    get_item_tags,
    get_or_create_tags,
    normalize,
    set_item_tags,
    tags_with_counts,
)
from tests.conftest import make_user


def test_duplicate_tag_returns_same_id(db_session):
    user = make_user(db_session, username="dupe")
    first = get_or_create_tags(db_session, user.id, ["python"])
    second = get_or_create_tags(db_session, user.id, ["python"])
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id
    all_tags = tags_with_counts(db_session, user.id)
    python_rows = [tag for tag, _ in all_tags if tag.name == "python"]
    assert len(python_rows) == 1


def test_normalize_tag_name():
    assert normalize("  Python ") == "python"
    assert normalize("TÜRKÇE") == "türkçe"


def test_comma_in_tag_name_raises():
    with pytest.raises(ValueError):
        normalize("py,thon")


def test_set_item_tags_clears_old_links(db_session):
    user = make_user(db_session, username="linker")
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Bağlantılar"))
    set_item_tags(db_session, user.id, item.id, ["python", "django"])
    names = sorted(t.name for t in get_item_tags(db_session, user.id, item.id))
    assert names == ["django", "python"]
    set_item_tags(db_session, user.id, item.id, ["flask"])
    names = [t.name for t in get_item_tags(db_session, user.id, item.id)]
    assert names == ["flask"]
    tags, _ = list_items(db_session, user.id)
    assert len(tags) == 1


def test_tag_filter_with_pagination(db_session):
    user = make_user(db_session, username="batch")
    for i in range(25):
        item = create_item(
            db_session, user.id, ItemCreate(type="note", title=f"Etiket Testi {i}")
        )
        if i < 10:
            set_item_tags(db_session, user.id, item.id, ["python"])
    items, has_next = list_items(db_session, user.id, tag="python", page=1, page_size=20)
    assert len(items) == 10
    assert has_next is False


def test_soft_deleted_item_not_in_tag_list(db_session):
    user = make_user(db_session, username="deleter")
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Çöpe"))
    set_item_tags(db_session, user.id, item.id, ["python"])
    toggle_flag(db_session, user.id, item.id, flag="deleted")
    items, has_next = list_items(db_session, user.id, tag="python", deleted=False)
    assert items == []
    assert has_next is False


def test_tags_with_counts(db_session):
    user = make_user(db_session, username="counter")
    i1 = create_item(db_session, user.id, ItemCreate(type="note", title="A1"))
    i2 = create_item(db_session, user.id, ItemCreate(type="note", title="A2"))
    i3 = create_item(db_session, user.id, ItemCreate(type="note", title="A3"))
    set_item_tags(db_session, user.id, i1.id, ["python"])
    set_item_tags(db_session, user.id, i2.id, ["python"])
    set_item_tags(db_session, user.id, i3.id, ["django"])
    result = sorted(
        (tag.name, count) for tag, count in tags_with_counts(db_session, user.id)
    )
    assert result == [("django", 1), ("python", 2)]
