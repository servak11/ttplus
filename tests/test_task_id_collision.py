"""
Regression test for issue #8 - "Item NNNNN already exists".

Task IDs are timestamp based with 1-second resolution: generate_task_id()
returns datetime.now() formatted as YYYYMMDDHHMMSS, and generate_short_task_id()
hashes it to a 5-char MD5 that is used BOTH as the TreeView iid and as the
work_tasks key.

If the user types the first letter of a new task within the same wall-clock
second that the placeholder row was created, add_new_task_placeholder() would
regenerate the identical short id and table1.insert(iid=...) raised
    _tkinter.TclError: Item NNNNN already exists

These tests reproduce that same-second scenario with a fake table that mimics
ttk.Treeview (its insert() rejects a duplicate iid) and assert that the
controller now produces unique ids instead of crashing.

The tests are hermetic: control.py imports web.flask_server (which pulls in
flask + markdown2). Those are stubbed if not installed so the pure ID logic can
be exercised without the GUI/web stack.
"""

import sys
import types
import unittest


# ---- stub heavy optional deps so `import control` works without them ---------

def _stub_module(name, **attrs):
    try:
        __import__(name)
        return
    except Exception:
        pass
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod


class _FakeFlask:
    def __init__(self, *args, **kwargs):
        pass

    def route(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def run(self, *args, **kwargs):
        pass


_stub_module("markdown2", markdown=lambda *a, **k: "")
_stub_module(
    "flask",
    Flask=_FakeFlask,
    request=types.SimpleNamespace(get_json=lambda *a, **k: {}),
    jsonify=lambda *a, **k: {},
    render_template_string=lambda *a, **k: "",
    send_file=lambda *a, **k: None,
    Response=object,
)

import control  # noqa: E402
from control import TTPlusController  # noqa: E402


# ---- fake Treeview that behaves like ttk.Treeview for the bits we use --------

class FakeTree:
    """Minimal stand-in for controls.tasktable.TableWidget / ttk.Treeview."""

    def __init__(self):
        self._order = []          # iids in insertion order
        self._values = {}         # iid -> list(values)
        self._tags = {}           # iid -> tuple(tags)
        self._selection = ()

    def insert(self, parent, index, iid=None, values=(), tags=()):
        # ttk.Treeview raises TclError when the iid already exists
        if iid in self._values:
            raise Exception(f"Item {iid} already exists")
        self._values[iid] = list(values)
        self._tags[iid] = tuple(tags)
        self._order.append(iid)
        return iid

    def get_children(self, item=""):
        return tuple(self._order)

    def item(self, iid, option=None, values=None, tags=None):
        if isinstance(iid, tuple):          # selection() returns a tuple
            iid = iid[0]
        if values is not None:
            self._values[iid] = list(values)
            return
        if tags is not None:
            self._tags[iid] = tuple(tags)
            return
        return {"values": list(self._values.get(iid, []))}

    def selection(self):
        return self._selection

    def selection_set(self, iid):
        self._selection = (iid,)

    def index(self, iid):
        return self._order.index(iid)


class FakeStatusBar:
    def s_set(self, *args):
        pass


class FakeEntry:
    def __init__(self, text=""):
        self._text = text

    def get(self):
        return self._text


class FakeView:
    def __init__(self):
        self.table1 = FakeTree()
        self.status_bar = FakeStatusBar()
        self.textfield_task_name = FakeEntry()


def make_controller():
    """Build a controller without running __init__ (no NoteServer / no DB file)."""
    c = TTPlusController.__new__(TTPlusController)
    c.view = FakeView()
    c.database = {"work_tasks": {}, "task_details": {}}
    return c


class SameSecondPatch:
    """Force generate_task_id() to return a fixed second, like fast typing."""

    def __init__(self, controller, fixed="20260721150650"):
        self.controller = controller
        self.fixed = fixed
        self._orig = None

    def __enter__(self):
        self._orig = self.controller.generate_task_id
        self.controller.generate_task_id = lambda: self.fixed
        return self

    def __exit__(self, *exc):
        self.controller.generate_task_id = self._orig


class TaskIdCollisionTest(unittest.TestCase):

    def test_two_placeholders_same_second_do_not_collide(self):
        """The exact crash site: two placeholders created in one second."""
        c = make_controller()
        with SameSecondPatch(c):
            id1 = c.add_new_task_placeholder()
            # would raise "Item ... already exists" before the fix
            id2 = c.add_new_task_placeholder()

        children = c.view.table1.get_children()
        self.assertEqual(len(children), 2)
        self.assertEqual(len(set(children)), 2, "iids must be unique")
        self.assertNotEqual(id1, id2, "returned seeds must differ")

    def test_returned_seed_hashes_to_the_inserted_iid(self):
        """
        update_task_name() rebuilds the id as md5(task_placeholder_id), so the
        returned seed must hash to the iid that was actually inserted, even after
        the collision workaround salted the seed.
        """
        c = make_controller()
        with SameSecondPatch(c):
            c.add_new_task_placeholder()               # occupies md5(fixed)
            seed = c.add_new_task_placeholder()         # must be salted

        expected_iid = c.generate_short_task_id(seed)
        self.assertIn(expected_iid, c.view.table1.get_children())

    def test_update_task_name_creates_task_without_crash(self):
        """
        End-to-end: select the placeholder, type a letter (create_new_task),
        which spawns a fresh placeholder in the same second. Must not crash and
        must leave exactly one real task plus one new placeholder.
        """
        c = make_controller()
        with SameSecondPatch(c):
            # startup placeholder (as populate_table1 would do)
            c.task_placeholder_id = c.add_new_task_placeholder()

            placeholder_iid = c.view.table1.get_children()[0]
            c.view.table1.selection_set(placeholder_iid)
            c.view.textfield_task_name = FakeEntry("B")

            c.update_task_name()   # first keystroke of a brand-new task

        # one real task recorded under the placeholder's short id
        self.assertEqual(len(c.database["work_tasks"]), 1)
        real_id = next(iter(c.database["work_tasks"]))
        self.assertEqual(c.database["work_tasks"][real_id]["tnm"], "B")

        # tree still shows the real task plus a brand-new (unique) placeholder
        children = c.view.table1.get_children()
        self.assertEqual(len(children), 2)
        self.assertEqual(len(set(children)), 2)


if __name__ == "__main__":
    unittest.main()
