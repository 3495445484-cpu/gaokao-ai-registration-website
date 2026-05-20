"""
农产品销售系统 - 用户登录校验模块

功能描述：
    提供用户身份验证功能，包括输入校验、用户存在性判断和密码验证。
    支持多种用户角色（管理员、销售者、客户）的登录验证。

版本信息：
    Version: 1.0
    Date: 2026-05-20
"""
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 定义常量，解决 SonarLint 重复字符串警告
ADMIN_PASSWORD = "admin123"
FARMER_PASSWORD = "farm@2024"
FARMER2_PASSWORD = "green@2024"
CUSTOMER1_PASSWORD = "user@2024"
CUSTOMER2_PASSWORD = "buy@2024"


class User:
    """
    用户类，存储用户基本信息
    """

    def __init__(self, username, password, user_type="customer"):
        self.username = username
        self.password = password
        self.user_type = user_type

    def __str__(self):
        return f"User(username={self.username}, type={self.user_type})"


class LoginValidator:
    """
    登录验证器类，处理用户登录校验的完整流程
    """

    def __init__(self):
        self.users_db = {
            "admin": User("admin", ADMIN_PASSWORD, "admin"),
            "farmer001": User("farmer001", FARMER_PASSWORD, "seller"),
            "farmer002": User("farmer002", FARMER2_PASSWORD, "seller"),
            "customer001": User("customer001", CUSTOMER1_PASSWORD, "customer"),
            "customer002": User("customer002", CUSTOMER2_PASSWORD, "customer")
        }

        self.failed_attempts = {}
        self.max_attempts = 5

    def validate_input(self, username, password):
        if username is None:
            return False, "用户名不能为None"

        if password is None:
            return False, "密码不能为None"

        username = str(username)
        password = str(password)

        if not username.strip():
            return False, "用户名不能为空"

        if not password.strip():
            return False, "密码不能为空"

        if len(username.strip()) < 3:
            return False, "用户名长度不能少于3个字符"

        if len(username.strip()) > 20:
            return False, "用户名长度不能超过20个字符"

        if len(password.strip()) < 6:
            return False, "密码长度不能少于6个字符"

        if len(password.strip()) > 30:
            return False, "密码长度不能超过30个字符"

        return True, ""

    def check_user_exists(self, username):
        return username in self.users_db

    def verify_password(self, username, password):
        try:
            user = self.users_db.get(username)
            if user is None:
                return False
            return user.password == password
        except Exception as e:
            logger.error(f"密码验证异常: {e}")
            return False

    def check_login_attempts(self, username):
        attempts = self.failed_attempts.get(username, 0)
        if attempts >= self.max_attempts:
            return False, f"登录失败次数过多（{self.max_attempts}次），账户已被临时锁定"
        return True, ""

    def record_failed_attempt(self, username):
        self.failed_attempts[username] = self.failed_attempts.get(username, 0) + 1

    def reset_failed_attempts(self, username):
        if username in self.failed_attempts:
            del self.failed_attempts[username]

    def login(self, username, password):
        result = {
            "success": False,
            "message": "",
            "user": None
        }

        try:
            is_valid, error_msg = self.validate_input(username, password)
            if not is_valid:
                result["message"] = f"输入验证失败: {error_msg}"
                return result

            clean_username = username.strip()
            clean_password = password.strip()

            is_allowed, attempt_msg = self.check_login_attempts(clean_username)
            if not is_allowed:
                result["message"] = attempt_msg
                return result

            if not self.check_user_exists(clean_username):
                self.record_failed_attempt(clean_username)
                result["message"] = "用户不存在，请先注册"
                return result

            if not self.verify_password(clean_username, clean_password):
                self.record_failed_attempt(clean_username)
                remaining = self.max_attempts - self.failed_attempts[clean_username]
                result["message"] = f"密码错误，请重试（剩余{remaining}次机会）"
                return result

            user = self.users_db[clean_username]
            self.reset_failed_attempts(clean_username)

            result["success"] = True
            result["message"] = f"欢迎回来，{clean_username}！"
            result["user"] = user

        except Exception as e:
            logger.error(f"登录异常: {str(e)}")
            result["message"] = "系统异常，请稍后重试"

        return result


def run_test_cases(validator):
    print("\n" + "=" * 60)
    print("                     自动化测试用例")
    print("=" * 60)

    test_cases = [
        {"name": "测试1: 管理员正确登录", "username": "admin", "password": ADMIN_PASSWORD, "expect_success": True},
        {"name": "测试2: 销售者正确登录", "username": "farmer001", "password": FARMER_PASSWORD, "expect_success": True},
        {"name": "测试3: 客户正确登录", "username": "customer001", "password": CUSTOMER1_PASSWORD,
         "expect_success": True},
        {"name": "测试4: 用户名为空", "username": "", "password": FARMER_PASSWORD, "expect_success": False},
        {"name": "测试5: 密码为空", "username": "farmer001", "password": "", "expect_success": False},
        {"name": "测试6: 用户名密码均为空", "username": "", "password": "", "expect_success": False},
        {"name": "测试7: 用户不存在", "username": "unknown", "password": "123456", "expect_success": False},
        {"name": "测试8: 密码错误", "username": "farmer001", "password": "wrong", "expect_success": False},
        {"name": "测试9: 用户名过短", "username": "ab", "password": "validpass", "expect_success": False},
        {"name": "测试10: 密码过短", "username": "farmer001", "password": "123", "expect_success": False},
    ]

    passed = 0
    for case in test_cases:
        print(f"\n[{case['name']}]")
        res = validator.login(case["username"], case["password"])
        if res["success"] == case["expect_success"]:
            print(f"  ✓ 测试通过 | {res['message']}")
            passed += 1
        else:
            print(f"  ✗ 测试失败 | {res['message']}")

    print(f"\n测试完成：通过 {passed}/{len(test_cases)}")


def interactive_login(validator):
    print("\n============ 农产品销售系统 - 登录 ============\n")
    while True:
        username = input("用户名：").strip()
        if username.lower() in ["quit", "exit"]:
            break
        password = input("密码：").strip()
        res = validator.login(username, password)
        if res["success"]:
            print(f"\n✓ 登录成功！{res['message']}")
            print(f"  用户类型：{res['user'].user_type}")
            break
        else:
            print(f"\n✗ 失败：{res['message']}\n")


def main():
    print("=" * 60)
    print("         农产品销售系统 - 用户登录校验模块")
    print("=" * 60)
    validator = LoginValidator()
    run_test_cases(validator)
    if input("\n进入登录界面？(y/n)：").lower() == "y":
        interactive_login(validator)
    else:
        print("程序结束。")


if __name__ == "__main__":
    main()