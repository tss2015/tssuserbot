from services.task_manager import TaskManager, UserTask

def test_task_manager():
    tm = TaskManager()
    item = UserTask("x", 1, 2)
    tm.add(item)
    assert tm.get(1) is item
    assert tm.cancel(1)
    assert item.cancel_event.is_set()
