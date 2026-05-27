"""
test_api.py — 餐饮管理系统 API 测试
测试框架: pytest + requests
覆盖: 正常用例、边界用例、异常用例，共 15 条
"""
import pytest
import requests
import sys
import io

# 解决 Windows 控制台 Unicode 输出问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://localhost:3000"
TOKEN = None
HEADERS = {}

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def login():
    """前置：登录获取 token"""
    global TOKEN, HEADERS
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    TOKEN = data["data"]["token"]
    HEADERS = {"x-auth-token": TOKEN, "Content-Type": "application/json"}


# ============================================================
# 一、正常用例
# ============================================================

class TestNormal:
    """正常功能测试"""

    def test_01_login_success(self):
        """TC01: 正确的用户名密码登录成功"""
        r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert data["data"]["username"] == "admin"
        assert data["data"]["role"] == "admin"
        assert "token" in data["data"]

    def test_02_get_menu(self):
        """TC02: 获取菜单列表"""
        r = requests.get(f"{BASE}/api/menu", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        # 验证菜品结构
        item = data["data"][0]
        assert "name" in item
        assert "price" in item
        assert "category" in item

    def test_03_get_tables(self):
        """TC03: 获取桌台列表"""
        r = requests.get(f"{BASE}/api/tables", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

    def test_04_get_dashboard_stats(self):
        """TC04: 获取仪表盘统计数据"""
        r = requests.get(f"{BASE}/api/dashboard/stats", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        stats = data["data"]
        assert "todayOrders" in stats
        assert "todayRevenue" in stats
        assert "memberCount" in stats

    def test_05_add_menu_item(self):
        """TC05: 添加新菜品"""
        r = requests.post(f"{BASE}/api/menu", headers=HEADERS, json={
            "name": "测试菜品_" + str(__import__("time").time()),
            "category": "热菜",
            "price": 25,
            "emoji": "🧪"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert "id" in data["data"]
        # 清理：下架测试菜品
        mid = data["data"]["id"]
        requests.put(f"{BASE}/api/menu/{mid}", headers=HEADERS, json={"status": 0})

    def test_06_get_members(self):
        """TC06: 获取会员列表"""
        r = requests.get(f"{BASE}/api/members", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    def test_07_get_combos(self):
        """TC07: 获取套餐列表"""
        r = requests.get(f"{BASE}/api/combos", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)


# ============================================================
# 二、边界用例
# ============================================================

class TestBoundary:
    """边界条件测试"""

    def test_08_login_empty_password(self):
        """TC08: 空密码登录（边界）"""
        r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ""})
        assert r.status_code == 401
        data = r.json()
        assert data["code"] == 401

    def test_09_order_minimum_items(self):
        """TC09: 下单单菜品最低数量"""
        r = requests.post(f"{BASE}/api/orders", headers=HEADERS, json={
            "tableNum": "A03",
            "items": [{"menuId": 1, "qty": 1, "note": ""}]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert data["data"]["total"] > 0

    def test_10_inventory_adjust_to_zero(self):
        """TC10: 库存调整至0（边界）"""
        # 先查一个库存项
        r = requests.get(f"{BASE}/api/inventory", headers=HEADERS)
        items = r.json()["data"]
        if len(items) > 0:
            inv_id = items[0]["id"]
            current_qty = items[0]["quantity"]
            r = requests.post(f"{BASE}/api/inventory/{inv_id}/adjust", headers=HEADERS, json={
                "change": -current_qty,
                "type": "out",
                "remark": "边界测试-清零"
            })
            assert r.status_code == 200
            data = r.json()
            assert data["code"] == 0
            assert data["data"]["newQuantity"] == 0
            # 恢复
            requests.post(f"{BASE}/api/inventory/{inv_id}/adjust", headers=HEADERS, json={
                "change": current_qty,
                "type": "in",
                "remark": "恢复"
            })

    def test_11_table_status_update(self):
        """TC11: 桌台状态切换（边界：空桌变占桌）"""
        r = requests.get(f"{BASE}/api/tables", headers=HEADERS)
        tables = r.json()["data"]
        empty_table = next((t for t in tables if t["status"] == "empty"), None)
        if empty_table:
            tid = empty_table["id"]
            r = requests.patch(f"{BASE}/api/tables/{tid}/status", headers=HEADERS, json={
                "status": "occupied", "customers": 2
            })
            assert r.status_code == 200
            assert r.json()["code"] == 0
            # 恢复
            requests.patch(f"{BASE}/api/tables/{tid}/status", headers=HEADERS, json={
                "status": "empty", "customers": 0
            })


# ============================================================
# 三、异常用例
# ============================================================

class TestAbnormal:
    """异常场景测试"""

    def test_12_login_wrong_password(self):
        """TC12: 错误的密码（异常）"""
        r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "wrongpassword123"})
        assert r.status_code == 401
        data = r.json()
        assert data["code"] == 401

    def test_13_create_menu_no_name(self):
        """TC13: 缺少必填字段创建菜品（异常）"""
        r = requests.post(f"{BASE}/api/menu", headers=HEADERS, json={
            "category": "热菜",
            "price": 20
        })
        assert r.status_code == 400
        data = r.json()
        assert data["code"] != 0

    def test_14_order_without_items(self):
        """TC14: 下单不传菜品（异常）"""
        r = requests.post(f"{BASE}/api/orders", headers=HEADERS, json={
            "tableNum": "A01",
            "items": []
        })
        assert r.status_code == 400
        data = r.json()
        assert data["code"] != 0

    def test_15_unauthorized_access(self):
        """TC15: 未认证访问受保护接口（异常）"""
        r = requests.get(f"{BASE}/api/menu")
        assert r.status_code == 401
        data = r.json()
        assert data["code"] == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
