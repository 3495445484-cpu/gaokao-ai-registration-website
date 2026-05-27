"""
run_tests.py — 直接运行测试并输出结果，绕过 shell 兼容性问题
"""
import requests
import json
import sys
import io
import traceback
from datetime import datetime

# 解决 Windows 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://localhost:3000"
results = []
passed = 0
failed = 0

def test(case_id, category, desc, func):
    global passed, failed
    try:
        func()
        passed += 1
        results.append({"id": case_id, "category": category, "desc": desc, "status": "PASS"})
    except Exception as e:
        failed += 1
        msg = str(e).split('\n')[0][:120]
        results.append({"id": case_id, "category": category, "desc": desc, "status": "FAIL", "error": msg})

def assert_status(r, code):
    assert r.status_code == code, f"期望 HTTP {code}, 实际 {r.status_code}"

def assert_code(r, code):
    data = r.json()
    assert data["code"] == code, f"期望 code={code}, 实际 code={data['code']}, msg={data.get('msg')}"

def assert_data_has(r, *keys):
    data = r.json()
    assert data["code"] == 0, f"API 返回失败: {data.get('msg')}"
    for k in keys:
        assert k in data["data"], f"返回 data 缺少字段: {k}"

# =================== 登录获取 token ===================
print("=" * 60)
print("  餐饮管理系统 API 测试报告")
print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  测试目标: {BASE}")
print("=" * 60)

r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
assert r.json()["code"] == 0, "前置登录失败"
TOKEN = r.json()["data"]["token"]
HEADERS = {"x-auth-token": TOKEN, "Content-Type": "application/json"}
print("🔑 登录成功，Token 已获取\n")

# =================== 正常用例 ===================
test("TC01", "正常", "正确用户名密码登录", lambda: (
    (r := requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})),
    assert_status(r, 200), assert_code(r, 0),
    None
)[-1])

test("TC02", "正常", "获取菜单列表", lambda: (
    (r := requests.get(f"{BASE}/api/menu", headers=HEADERS)),
    assert_status(r, 200), assert_code(r, 0),
    len(r.json()["data"]) > 0 or (_ for _ in ()).throw(AssertionError("菜单列表为空"))
))

test("TC03", "正常", "获取桌台列表", lambda: (
    (r := requests.get(f"{BASE}/api/tables", headers=HEADERS)),
    assert_status(r, 200), assert_code(r, 0),
    len(r.json()["data"]) > 0 or (_ for _ in ()).throw(AssertionError("桌台列表为空"))
))

test("TC04", "正常", "获取仪表盘统计数据", lambda: (
    (r := requests.get(f"{BASE}/api/dashboard/stats", headers=HEADERS)),
    assert_status(r, 200), assert_code(r, 0),
    assert_data_has(r, "todayOrders", "todayRevenue", "memberCount")
))

test("TC05", "正常", "添加新菜品", lambda: (
    (r := requests.post(f"{BASE}/api/menu", headers=HEADERS,
        json={"name": f"测试菜品_{int(datetime.now().timestamp())}", "category": "热菜", "price": 25, "emoji": "\U0001f9ea"})),
    assert_status(r, 200), assert_code(r, 0),
    "id" in r.json()["data"] or (_ for _ in ()).throw(AssertionError("未返回 id")),
    # 清理
    requests.put(f"{BASE}/api/menu/{r.json()['data']['id']}", headers=HEADERS, json={"status": 0})
))

test("TC06", "正常", "获取会员列表", lambda: (
    (r := requests.get(f"{BASE}/api/members", headers=HEADERS)),
    assert_status(r, 200), assert_code(r, 0)
))

test("TC07", "正常", "获取套餐列表", lambda: (
    (r := requests.get(f"{BASE}/api/combos", headers=HEADERS)),
    assert_status(r, 200), assert_code(r, 0)
))

test("TC08", "正常", "获取订单列表", lambda: (
    (r := requests.get(f"{BASE}/api/orders", headers=HEADERS)),
    assert_status(r, 200), assert_code(r, 0)
))

# =================== 边界用例 ===================
test("TC09", "边界", "空密码登录（返回 400 Bad Request）", lambda: (
    (r := requests.post(f"{BASE}/api/auth/login",
        json={"username": "admin", "password": ""})),
    assert_status(r, 400),
    r.json()["code"] != 0 or (_ for _ in ()).throw(AssertionError("空密码应返回错误"))
))

test("TC10", "边界", "最小数量下单（1菜品×1份）", lambda: (
    (r := requests.post(f"{BASE}/api/orders", headers=HEADERS,
        json={"tableNum": "A03", "items": [{"menuId": 1, "qty": 1, "note": "边界测试-最小订单"}]})),
    assert_status(r, 200), assert_code(r, 0),
    r.json()["data"]["total"] > 0 or (_ for _ in ()).throw(AssertionError("订单金额为0"))
))

test("TC11", "边界", "库存调整归零（newQuantity=0）", lambda: (
    (inv_list := requests.get(f"{BASE}/api/inventory", headers=HEADERS).json()["data"]),
    len(inv_list) > 0 or (_ for _ in ()).throw(AssertionError("无库存数据")),
    (item := inv_list[0]),
    (orig_qty := item["quantity"]),
    (r := requests.post(f"{BASE}/api/inventory/{item['id']}/adjust", headers=HEADERS,
        json={"change": -orig_qty, "type": "out", "remark": "边界测试-归零"})),
    assert_status(r, 200), assert_code(r, 0),
    r.json()["data"]["newQuantity"] == 0 or (_ for _ in ()).throw(AssertionError("未归零")),
    # 恢复
    requests.post(f"{BASE}/api/inventory/{item['id']}/adjust", headers=HEADERS,
        json={"change": orig_qty, "type": "in", "remark": "恢复"})
))

test("TC12", "边界", "低库存预警查询", lambda: (
    (r := requests.get(f"{BASE}/api/inventory/low-stock", headers=HEADERS)),
    assert_status(r, 200), assert_code(r, 0)
))

# =================== 异常用例 ===================
test("TC13", "异常", "错误密码登录（返回 401）", lambda: (
    (r := requests.post(f"{BASE}/api/auth/login",
        json={"username": "admin", "password": "WRONG_PASSWORD_123456"})),
    assert_status(r, 401),
    r.json()["code"] != 0 or (_ for _ in ()).throw(AssertionError("错误密码应拒绝"))
))
test("TC14", "异常", "缺少必填字段（菜单缺name）", lambda: (
    (r := requests.post(f"{BASE}/api/menu", headers=HEADERS, json={"category": "热菜", "price": 20})),
    assert_status(r, 400),
    r.json()["code"] != 0 or (_ for _ in ()).throw(AssertionError("缺name应报错"))
))
test("TC15", "异常", "空菜品下单", lambda: (
    (r := requests.post(f"{BASE}/api/orders", headers=HEADERS,
        json={"tableNum": "A01", "items": []})),
    assert_status(r, 400),
    r.json()["code"] != 0 or (_ for _ in ()).throw(AssertionError("空菜品应报错"))
))
test("TC16", "异常", "未认证访问（无Token）", lambda: (
    (r := requests.get(f"{BASE}/api/menu")),
    assert_status(r, 401),
    r.json()["code"] == 401 or (_ for _ in ()).throw(AssertionError("未认证应拒绝"))
))
test("TC17", "异常", "空姓名注册会员", lambda: (
    (r := requests.post(f"{BASE}/api/members", headers=HEADERS, json={"name": "", "phone": ""})),
    assert_status(r, 400),
    r.json()["code"] != 0 or (_ for _ in ()).throw(AssertionError("空姓名电话应报错"))
))
# =================== 汇总 ===================
# 按类别分组
categories = [
    ("正常", "正常用例"),
    ("边界", "边界用例"),
    ("异常", "异常用例"),
]

print("\n" + "=" * 42)
print("  测试结果汇总")
print(f"  总计: {passed + failed}  通过: {passed}  失败: {failed}")
print("=" * 42)

for cat_key, cat_label in categories:
    cat_results = [r for r in results if r["category"] == cat_key]
    pass_count = sum(1 for r in cat_results if r["status"] == "PASS")
    icon = "✅" if pass_count == len(cat_results) else "⚠️"
    print(f"\n【{cat_label}】{len(cat_results)} 条全部通过：" if pass_count == len(cat_results) else f"\n【{cat_label}】{len(cat_results)} 条（通过 {pass_count}，失败 {len(cat_results) - pass_count}）：")
    for r in cat_results:
        mark = "✅" if r["status"] == "PASS" else "❌"
        if r["status"] == "FAIL":
            print(f"{mark} {r['id']} {r['desc']}  -> {r['error']}")
        else:
            print(f"{mark} {r['id']} {r['desc']}")
print()

# 输出 JSON 供报告使用
report = {
    "base": BASE,
    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "total": passed + failed,
    "passed": passed,
    "failed": failed,
    "results": results,
    "test_cases": [
        {"id": "TC01", "category": "正常", "target": "正确用户名密码登录", "method": "POST /api/auth/login", "input": '{"username":"admin","password":"admin123"}', "expected": "返回 code=0, token 和用户信息"},
        {"id": "TC02", "category": "正常", "target": "获取菜单列表", "method": "GET /api/menu", "input": "无", "expected": "返回菜品列表数组，非空"},
        {"id": "TC03", "category": "正常", "target": "获取桌台列表", "method": "GET /api/tables", "input": "无", "expected": "返回桌台列表数组，非空"},
        {"id": "TC04", "category": "正常", "target": "获取仪表盘统计", "method": "GET /api/dashboard/stats", "input": "无", "expected": "返回营收、订单数、会员数等"},
        {"id": "TC05", "category": "正常", "target": "添加新菜品", "method": "POST /api/menu", "input": '{"name":"测试_xxx","category":"热菜","price":25}', "expected": "返回 code=0, 返回新菜品 id"},
        {"id": "TC06", "category": "正常", "target": "获取会员列表", "method": "GET /api/members", "input": "无", "expected": "返回会员列表数组"},
        {"id": "TC07", "category": "正常", "target": "获取套餐列表", "method": "GET /api/combos", "input": "无", "expected": "返回套餐列表数组"},
        {"id": "TC08", "category": "正常", "target": "获取订单列表", "method": "GET /api/orders", "input": "无", "expected": "返回订单列表数组"},
        {"id": "TC09", "category": "边界", "target": "空密码登录", "method": "POST /api/auth/login", "input": '{"username":"admin","password":""}', "expected": "HTTP 401, code≠0"},
        {"id": "TC10", "category": "边界", "target": "最小数量下单", "method": "POST /api/orders", "input": '{"tableNum":"A03","items":[{"menuId":1,"qty":1}]}', "expected": "code=0, total>0"},
        {"id": "TC11", "category": "边界", "target": "库存调整归零", "method": "POST /api/inventory/:id/adjust", "input": '{"change":-currentQty}', "expected": "newQuantity=0"},
        {"id": "TC12", "category": "边界", "target": "低库存预警查询", "method": "GET /api/inventory/low-stock", "input": "无", "expected": "返回低于安全线的库存列表"},
        {"id": "TC13", "category": "异常", "target": "错误密码登录", "method": "POST /api/auth/login", "input": '{"username":"admin","password":"wrong"}', "expected": "HTTP 401, 拒绝访问"},
        {"id": "TC14", "category": "异常", "target": "缺少必填字段", "method": "POST /api/menu", "input": '{"category":"热菜","price":20}', "expected": "HTTP 400, code≠0"},
        {"id": "TC15", "category": "异常", "target": "空菜品下单", "method": "POST /api/orders", "input": '{"tableNum":"A01","items":[]}', "expected": "HTTP 400, code≠0"},
        {"id": "TC16", "category": "异常", "target": "未认证访问", "method": "GET /api/menu", "input": "无 Token", "expected": "HTTP 401, code=401"},
        {"id": "TC17", "category": "异常", "target": "空姓名注册会员", "method": "POST /api/members", "input": '{"name":"","phone":""}', "expected": "HTTP 400, code≠0"},
    ]
}

with open("test_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("📄 测试报告已保存到 test_report.json")
