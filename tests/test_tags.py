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


def test_rename_tag(db_session):
    from cepearsiv.services.tags import rename_tag

    user = make_user(db_session, username="renamer")
    (tag,) = get_or_create_tags(db_session, user.id, ["python"])
    item = create_item(db_session, user.id, ItemCreate(type="note", title="Ad Degisti"))
    set_item_tags(db_session, user.id, item.id, ["python"])
    renamed = rename_tag(db_session, user.id, tag.id, "py")
    assert renamed.name == "py"
    names = [t.name for t in get_item_tags(db_session, user.id, item.id)]
    assert names == ["py"]


def test_rename_tag_normalizes_input(db_session):
    from cepearsiv.services.tags import rename_tag

    user = make_user(db_session, username="renamer2")
    (tag,) = get_or_create_tags(db_session, user.id, ["python"])
    renamed = rename_tag(db_session, user.id, tag.id, "  Pythonista ")
    assert renamed.name == "pythonista"


def test_rename_to_same_name_is_noop(db_session):
    from cepearsiv.services.tags import rename_tag

    user = make_user(db_session, username="renamer3")
    (tag,) = get_or_create_tags(db_session, user.id, ["python"])
    renamed = rename_tag(db_session, user.id, tag.id, "PYTHON")
    assert renamed.name == "python"


def test_rename_tag_conflict_raises(db_session):
    from cepearsiv.services.tags import rename_tag

    user = make_user(db_session, username="conflict")
    (tag,) = get_or_create_tags(db_session, user.id, ["python"])
    get_or_create_tags(db_session, user.id, ["py"])
    with pytest.raises(ValueError):
        rename_tag(db_session, user.id, tag.id, "py")


def test_rename_tag_missing_raises(db_session):
    from cepearsiv.services.tags import rename_tag

    user = make_user(db_session, username="ghost")
    with pytest.raises(ValueError):
        rename_tag(db_session, user.id, 99999, "hayalet")


def test_rename_tag_other_user_raises(db_session):
    from cepearsiv.services.tags import rename_tag

    a = make_user(db_session, username="usrA")
    b = make_user(db_session, username="usrB")
    (tag,) = get_or_create_tags(db_session, a.id, ["python"])
    with pytest.raises(ValueError):
        rename_tag(db_session, b.id, tag.id, "py")


def test_merge_tags_moves_links(db_session):
    from cepearsiv.services.tags import merge_tags

    user = make_user(db_session, username="merger")
    (src,) = get_or_create_tags(db_session, user.id, ["django"])
    (dst,) = get_or_create_tags(db_session, user.id, ["python"])
    i1 = create_item(db_session, user.id, ItemCreate(type="note", title="Bir"))
    i2 = create_item(db_session, user.id, ItemCreate(type="note", title="Iki"))
    set_item_tags(db_session, user.id, i1.id, ["django"])
    set_item_tags(db_session, user.id, i2.id, ["django", "python"])
    merge_tags(db_session, user.id, src.id, dst.id)
    names1 = [t.name for t in get_item_tags(db_session, user.id, i1.id)]
    names2 = [t.name for t in get_item_tags(db_session, user.id, i2.id)]
    assert names1 == ["python"]
    assert names2 == ["python"]
    counts = [(t.name, c) for t, c in tags_with_counts(db_session, user.id)]
    assert counts == [("python", 2)]


def test_merge_tags_same_id_raises(db_session):
    from cepearsiv.services.tags import merge_tags

    user = make_user(db_session, username="selfmerge")
    (tag,) = get_or_create_tags(db_session, user.id, ["python"])
    with pytest.raises(ValueError):
        merge_tags(db_session, user.id, tag.id, tag.id)


def test_merge_tags_missing_source_raises(db_session):
    from cepearsiv.services.tags import merge_tags

    user = make_user(db_session, username="missingmerge")
    (dst,) = get_or_create_tags(db_session, user.id, ["python"])
    with pytest.raises(ValueError):
        merge_tags(db_session, user.id, 99999, dst.id)


def test_merge_tags_other_user_raises(db_session):
    from cepearsiv.services.tags import merge_tags

    a = make_user(db_session, username="mergeA")
    b = make_user(db_session, username="mergeB")
    (src,) = get_or_create_tags(db_session, a.id, ["django"])
    (dst,) = get_or_create_tags(db_session, a.id, ["python"])
    with pytest.raises(ValueError):
        merge_tags(db_session, b.id, src.id, dst.id)
