from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
PANELS = (ROOT / "static" / "panels.js").read_text(encoding="utf-8")


def test_create_form_exposes_supported_backend_fields_and_is_not_title_only():
    for token in (
        'id="kanbanNewTaskBody"',
        'id="kanbanNewTaskAssignee"',
        'id="kanbanNewTaskPriority"',
        'id="kanbanNewTaskTenant"',
        'id="kanbanNewTaskStatus"',
        'id="kanbanNewTaskParents"',
        'id="kanbanNewTaskWorkspacePath"',
        'id="kanbanNewTaskSkills"',
    ):
        assert token in INDEX
    assert "JSON.stringify({title})" not in PANELS, "createKanbanTask must send more than the title"


def test_task_detail_panel_exposes_editors_for_patchable_fields_and_links():
    for token in (
        'id="kanbanTaskEditTitle"',
        'id="kanbanTaskEditBody"',
        'id="kanbanTaskEditAssignee"',
        'id="kanbanTaskEditPriority"',
        'id="kanbanTaskEditTenant"',
        'id="kanbanTaskLinkParent"',
        'id="kanbanTaskLinkChild"',
    ):
        assert token in PANELS
    assert "async function saveKanbanTaskEdits" in PANELS
    assert "async function linkKanbanTasks" in PANELS
    assert "async function unlinkKanbanTasks" in PANELS
    assert "'/api/kanban/links'" in PANELS
    assert "'/api/kanban/links/delete'" in PANELS


def test_dispatcher_contract_removes_running_shortcuts_and_uses_real_dispatch():
    assert '<option value="running">Running</option>' not in INDEX
    assert "quickKanbanCardAction(event,'${id}','running')" not in PANELS
    assert "dry_run=1" not in PANELS
    assert "async function nudgeKanbanDispatcher" in PANELS
