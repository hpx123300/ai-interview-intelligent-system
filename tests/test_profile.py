"""个人档案测试：默认档案、保存/加载回读、档案上下文文本。"""

from backend.app.db import UserProfile, get_session, init_db
from backend.app.profile import ProfileStore, profile_context_text

init_db()

TEST_KEY = "test_profile_key"


def _cleanup():
    with get_session() as session:
        row = session.get(UserProfile, TEST_KEY)
        if row is not None:
            session.delete(row)
            session.commit()


def test_profile_save_load_roundtrip():
    _cleanup()
    store = ProfileStore(TEST_KEY)
    default = store.load()
    assert default["target_role"] == "大模型 / AI 应用开发实习生"
    assert len(default["projects"]) == 3

    updated = store.save(
        {
            "target_role": "Python 后端实习生",
            "target_direction": "Python 后端",
            "skills": ["Python", "FastAPI"],
            "weak_areas": ["算法"],
            "projects": [
                {"name": "测试项目", "tech_stack": "Python", "description": "描述", "metrics": "指标", "story": "故事"}
            ],
        }
    )
    assert updated["target_role"] == "Python 后端实习生"
    assert updated["skills"] == ["Python", "FastAPI"]
    assert updated["projects"][0]["name"] == "测试项目"

    reloaded = store.load()
    assert reloaded["projects"][0]["name"] == "测试项目"
    _cleanup()


def test_profile_context_text_contains_projects():
    profile = ProfileStore().load()
    text = profile_context_text(profile)
    assert "目标岗位" in text
    assert "投满分" in text
    assert "AI 面试备战助手" in text
