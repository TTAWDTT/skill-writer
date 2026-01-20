#!/usr/bin/env python
"""
Skill Writer 后端测试脚本
测试主要 API 端点
"""
import sys
import os

# 将项目根目录添加到 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def test_imports():
    """测试模块导入"""
    print("Testing imports...")
    try:
        from backend.config import settings
        print(f"  [OK] Config loaded: {settings.APP_NAME} v{settings.APP_VERSION}")
    except Exception as e:
        print(f"  [FAIL] Config: {e}")
        return False

    try:
        from backend.api.main import app
        print(f"  [OK] FastAPI app created")
    except Exception as e:
        print(f"  [FAIL] FastAPI app: {e}")
        return False

    try:
        from backend.core.skills.registry import init_skills_from_directory, get_registry
        count = init_skills_from_directory()
        print(f"  [OK] Skills loaded: {count} skills")

        registry = get_registry()
        for skill in registry.get_all():
            print(f"      - {skill.metadata.id}: {skill.metadata.name}")
    except Exception as e:
        print(f"  [FAIL] Skills: {e}")
        return False

    try:
        from backend.models.database import get_database
        db = get_database()
        print(f"  [OK] Database initialized")
    except Exception as e:
        print(f"  [FAIL] Database: {e}")
        return False

    try:
        from backend.core.workflow import get_workflow
        workflow = get_workflow()
        print(f"  [OK] Workflow initialized")
    except Exception as e:
        print(f"  [FAIL] Workflow: {e}")
        return False

    return True


def test_skill_loading():
    """测试 Skill 加载"""
    print("\nTesting skill loading...")
    from backend.core.skills.registry import get_registry

    registry = get_registry()

    # 测试获取 NSFC skill
    nsfc = registry.get("nsfc-proposal-writer")
    if nsfc:
        print(f"  [OK] NSFC skill loaded")
        print(f"      Sections: {len(nsfc.structure)}")
        print(f"      Fields: {len(nsfc.requirement_fields)}")
        print(f"      Has guidelines: {len(nsfc.writing_guidelines) > 0}")
    else:
        print(f"  [FAIL] NSFC skill not found")
        return False

    # 测试获取 creator skill
    creator = registry.get("writer-skill-creator")
    if creator:
        print(f"  [OK] Creator skill loaded")
        print(f"      Has content: {len(creator.skill_content) > 0}")
    else:
        print(f"  [FAIL] Creator skill not found")
        return False

    return True


def test_api_routes():
    """测试 API 路由注册"""
    print("\nTesting API routes...")
    from backend.api.main import app

    routes = [route.path for route in app.routes]

    expected_routes = [
        "/",
        "/health",
        "/api/skills",
        "/api/chat/start",
        "/api/sessions",
    ]

    for route in expected_routes:
        found = any(route in r for r in routes)
        if found:
            print(f"  [OK] Route: {route}")
        else:
            print(f"  [WARN] Route not found: {route}")

    return True


if __name__ == "__main__":
    print("=" * 50)
    print("Skill Writer Backend Test")
    print("=" * 50)

    all_passed = True

    if not test_imports():
        all_passed = False

    if not test_skill_loading():
        all_passed = False

    if not test_api_routes():
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("All tests passed!")
        print("\nTo start the server, run:")
        print("  python run.py")
        print("\nOr double-click: start_backend.bat")
    else:
        print("Some tests failed!")
        sys.exit(1)
