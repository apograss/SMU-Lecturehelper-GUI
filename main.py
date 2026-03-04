import re
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from getpass import getpass
from io import BytesIO
from urllib.parse import parse_qs, urlparse
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from bs4 import BeautifulSoup, FeatureNotFound
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from PIL import Image
from requests.adapters import HTTPAdapter

CAPTCHA_URL = "https://zhjw.smu.edu.cn/yzm?d="
LOGIN_URL = "https://zhjw.smu.edu.cn/new/login"
PORTAL_URL = "https://zhjw.smu.edu.cn/"
WELCOME_URL = "https://zhjw.smu.edu.cn/new/welcome.page?ui=new"
XK_ROOT_URL = "https://zhjw.smu.edu.cn/new/student/xsxk/"
REQUEST_TIMEOUT = (1.5, 2.5)
ORDER_TIMEOUT = (0.8, 1.2)
MAX_ATTEMPTS = 120
PRIMARY_BURST_ATTEMPTS = 12
RETRY_INTERVAL_SECONDS = 0.0
SEND_AHEAD_SECONDS = 0.05

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Host": "zhjw.smu.edu.cn",
    "Referer": "https://zhjw.smu.edu.cn/",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

Logger = Callable[[str], None]


def build_session() -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def request_with_timeout(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return session.request(method, url, **kwargs)


def encrypt_password(password: str, verifycode: str) -> str:
    key = (verifycode * 4).encode("utf-8")
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(password.encode("utf-8"), AES.block_size))
    return encrypted.hex()


def is_login_page(text: str) -> bool:
    required_keywords = ("统一认证登录", "扫码登录", "密码登录")
    return all(keyword in text for keyword in required_keywords)


def verify_authenticated_session(session: requests.Session, logger: Logger = print) -> bool:
    try:
        verify_response = request_with_timeout(session, "GET", WELCOME_URL)
    except requests.RequestException as exc:
        logger(f"会话校验请求失败: {exc}")
        return False
    return not is_login_page(verify_response.text)


def apply_cookie_header(session: requests.Session, cookie_text: str) -> int:
    raw = cookie_text.strip()
    if raw.lower().startswith("cookie:"):
        raw = raw[7:].strip()
    raw = raw.strip().strip(";")
    if not raw:
        return 0
    if "=" not in raw and ";" not in raw:
        # Allow direct paste of JSESSIONID value from browser plugins.
        raw = f"JSESSIONID={raw}"

    count = 0
    for part in raw.replace("\n", ";").split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not value:
            continue
        session.cookies.set(name, value, domain="zhjw.smu.edu.cn", path="/")
        count += 1
    return count


def login_with_cookie(
    cookie_text: str,
    session: requests.Session,
    logger: Logger = print,
) -> bool:
    session.cookies.clear()
    cookie_count = apply_cookie_header(session, cookie_text)
    if cookie_count == 0:
        logger("Cookie 为空或格式无法解析。可直接粘贴 JSESSIONID 值。")
        return False
    logger(f"已导入 {cookie_count} 个 Cookie，正在校验会话...")

    if not verify_authenticated_session(session, logger=logger):
        logger("Cookie 会话无效（仍在登录页）。请从浏览器重新复制最新 Cookie。")
        return False
    logger("Cookie 登录成功。")
    return True


def fetch_captcha_bytes(session: requests.Session) -> bytes:
    captcha_response = request_with_timeout(
        session,
        "GET",
        CAPTCHA_URL + str(int(time.time() * 1000)),
    )
    captcha_response.raise_for_status()
    return captcha_response.content


def fetch_captcha_image(session: requests.Session) -> Image.Image:
    return Image.open(BytesIO(fetch_captcha_bytes(session)))


def get_captcha(session: requests.Session) -> str:
    img = fetch_captcha_image(session)
    img.show()
    captcha = input("请输入验证码: ").strip()
    img.close()
    return captcha


def login(
    account: str,
    password: str,
    captcha: str,
    session: requests.Session,
    logger: Logger = print,
) -> requests.Response | None:
    encrypted_password = encrypt_password(password, captcha)
    data = {
        "account": account,
        "pwd": encrypted_password,
        "verifycode": captcha,
    }
    try:
        response = request_with_timeout(session, "POST", LOGIN_URL, data=data)
    except requests.RequestException as exc:
        logger(f"登录请求失败: {exc}")
        return None

    login_ok = False
    if response.status_code == 200:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            message = str(payload.get("message", ""))
            login_ok = payload.get("code") == 0 or "成功" in message
        else:
            login_ok = "成功" in response.text

    if not login_ok:
        logger(f"登录失败，状态码: {response.status_code}")
        logger(response.text[:200])
        return None

    if not verify_authenticated_session(session, logger=logger):
        logger("登录接口返回成功，但当前会话未生效（仍在登录页）。")
        logger("请确认验证码正确，或改用 Cookie 登录（先在浏览器扫码/登录后复制 Cookie）。")
        return None

    logger("登录成功")
    return response


def calibration(session: requests.Session, samples: int = 3, logger: Logger = print) -> timedelta:
    best_diff = timedelta(0)
    best_rtt = None
    for _ in range(samples):
        try:
            response = request_with_timeout(session, "GET", WELCOME_URL)
        except requests.RequestException:
            continue
        date_header = response.headers.get("Date")
        if not date_header:
            continue
        server_dt_utc = parsedate_to_datetime(date_header).astimezone(timezone.utc)
        rtt_half = response.elapsed / 2
        local_recv_utc = datetime.now(timezone.utc)
        diff = (server_dt_utc + rtt_half) - local_recv_utc
        if best_rtt is None or response.elapsed < best_rtt:
            best_rtt = response.elapsed
            best_diff = diff
        time.sleep(0.03)
    logger(f"时间差值(秒，服务器-本地)：{best_diff.total_seconds():.6f}")
    try:
        shanghai_now = datetime.now(ZoneInfo("Asia/Shanghai"))
        logger(f"当前本地 Asia/Shanghai: {shanghai_now}")
    except ZoneInfoNotFoundError:
        logger("当前环境缺少 Asia/Shanghai 时区数据，改用本地系统时间。")
        logger(f"当前本地时间: {datetime.now()}")
    return best_diff


def parse_html(content: bytes, logger: Logger = print) -> BeautifulSoup:
    try:
        return BeautifulSoup(content, "lxml")
    except FeatureNotFound:
        logger("未检测到 lxml 解析器，已降级到 html.parser。")
        return BeautifulSoup(content, "html.parser")


def extract_category_code(link: str) -> str | None:
    if not link:
        return None
    match = re.search(r"/xklx/(\d+)", link)
    if match:
        return match.group(1)
    match = re.search(r"[?&]xklxdm=(\d+)", link)
    if match:
        return match.group(1)
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    xklxdm_values = query.get("xklxdm")
    if xklxdm_values:
        return xklxdm_values[0]
    return None


def collect_category_candidates(soup: BeautifulSoup, html_text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for element in soup.find_all(True):
        link = (
            element.get("data-href")
            or element.get("href")
            or element.get("onclick")
            or ""
        )
        code = extract_category_code(link)
        if not code:
            continue
        title = (
            element.get("lay-iframe")
            or element.get("title")
            or element.get_text(strip=True)
            or f"类型{code}"
        )
        key = (code, title)
        if key not in seen:
            seen.add(key)
            candidates.append(key)

    script_links = re.findall(r"""['"]([^'"]*(?:xklx|xklxdm)[^'"]*)['"]""", html_text)
    for script_link in script_links:
        code = extract_category_code(script_link)
        if not code:
            continue
        key = (code, f"类型{code}")
        if key not in seen:
            seen.add(key)
            candidates.append(key)

    return candidates


def get_course_category(
    session: requests.Session,
    logger: Logger = print,
) -> dict[int, dict[str, str]]:
    request_with_timeout(session, "GET", WELCOME_URL)
    response = request_with_timeout(session, "GET", XK_ROOT_URL)
    response.raise_for_status()
    if is_login_page(response.text):
        raise RuntimeError("当前会话无效或已过期，选课页被重定向到登录页。")
    soup = parse_html(response.content, logger=logger)
    logger("选课类型：")
    coursedict: dict[int, dict[str, str]] = {}
    candidates = collect_category_candidates(soup, response.text)

    for output_index, (code, title) in enumerate(candidates, start=1):
        coursedict[output_index] = {"code": code, "title": title}
        logger(f"{output_index}. {title}")

    if not coursedict:
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        preview = page_text[:160] if page_text else "页面无可读文本"
        raise RuntimeError(f"未找到选课类型。页面提示片段：{preview}")
    return coursedict


def get_course_list(
    session: requests.Session,
    coursecateurl: str,
    logger: Logger = print,
) -> tuple[list[dict], str]:
    courselisturl = coursecateurl + "/kxkc"
    payload = {
        "page": 1,
        "rows": 50,
        "sort": "kcrwdm",
        "order": "asc",
    }
    response = request_with_timeout(session, "POST", courselisturl, data=payload)
    responsetext = response.json()
    total = responsetext["total"]
    courses = list(responsetext["rows"])
    while len(courses) < total:
        payload["page"] += 1
        response = request_with_timeout(session, "POST", courselisturl, data=payload)
        courses.extend(response.json()["rows"])
    logger(f"已加载课程 {len(courses)} 门。")
    for idx, course in enumerate(courses, start=1):
        logger(f"{idx}. {course.get('kcmc', '')} {course.get('teaxm', '')}")
    return courses, coursecateurl


def order_course(session: requests.Session, kcrwdm: str, kcmc: str, url: str, hlct: int = 0) -> requests.Response:
    add_url = url + "/add"
    payload = {
        "kcrwdm": kcrwdm,
        "kcmc": kcmc,
        "qz": -1,
        "xxyqdm": "",
        "hlct": hlct,
    }
    return request_with_timeout(session, "POST", add_url, data=payload, timeout=ORDER_TIMEOUT)


def select_job(
    preferred_orders: list[int | None],
    session: requests.Session,
    courses: list[dict],
    coursecateurl: str,
    logger: Logger = print,
) -> bool:
    """
    高频抢课策略：
    1. 前几次只抢第一志愿
    2. 后续按有效志愿顺序轮询（最多支持 4 个）
    """
    orders: list[int] = []
    for order in preferred_orders:
        if order is None:
            continue
        if not (1 <= order <= len(courses)):
            logger(f"忽略越界志愿序号: {order}")
            continue
        if order not in orders:
            orders.append(order)

    if not orders:
        logger("没有有效志愿，取消抢课。")
        return False

    last_message = ""
    for i in range(MAX_ATTEMPTS):
        if i < PRIMARY_BURST_ATTEMPTS:
            order = orders[0]
        else:
            round_idx = (i - PRIMARY_BURST_ATTEMPTS) % len(orders)
            order = orders[round_idx]
        course = courses[order - 1]
        try:
            resp = order_course(
                session,
                course["kcrwdm"],
                course["kcmc"],
                coursecateurl,
            )
            resptext = resp.json()
        except requests.RequestException as exc:
            last_message = f"请求异常: {exc}"
            continue
        except ValueError:
            last_message = "响应非 JSON，可能被网关限流"
            continue

        code = resptext.get("code")
        msg = str(resptext.get("message", ""))
        last_message = msg or str(resptext)

        if code == 0 or msg == "您已经选了该门课程":
            logger(f"选课成功：{course.get('kcmc', '')}")
            return True
        if msg == "超出选课要求门数(1.0门)":
            logger("你已经达到选课上限。")
            return True

        # 检测冲突提示，自动确认（模拟点击弹窗"确定"按钮）
        if "冲突" in msg:
            logger(f"检测到冲突提示，自动确认: {msg}")
            try:
                resp2 = order_course(
                    session, course["kcrwdm"], course["kcmc"],
                    coursecateurl, hlct=1,
                )
                resptext2 = resp2.json()
                code2 = resptext2.get("code")
                msg2 = str(resptext2.get("message", ""))
                last_message = msg2 or str(resptext2)
                if code2 == 0 or msg2 == "您已经选了该门课程":
                    logger(f"选课成功（忽略冲突）：{course.get('kcmc', '')}")
                    return True
                if msg2 == "超出选课要求门数(1.0门)":
                    logger("你已经达到选课上限。")
                    return True
                logger(f"确认冲突后仍失败: {last_message}")
            except requests.RequestException as exc:
                logger(f"确认冲突请求异常: {exc}")
            except ValueError:
                logger("确认冲突响应非 JSON")

        if RETRY_INTERVAL_SECONDS > 0:
            time.sleep(RETRY_INTERVAL_SECONDS)

    logger(f"什么都没抢到，最后返回：{last_message}")
    return False


def compute_run_at(selection_time_str: str, time_diff: timedelta) -> datetime:
    selection_time = datetime.strptime(selection_time_str, "%H:%M:%S").time()
    selection_dt_local = datetime.combine(date.today(), selection_time)
    run_at_server = selection_dt_local - time_diff - timedelta(seconds=SEND_AHEAD_SECONDS)
    if run_at_server <= datetime.now():
        run_at_server = datetime.now() + timedelta(seconds=0.05)
    return run_at_server


def read_int(prompt: str, min_value: int, max_value: int) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("请输入数字。")
            continue
        if min_value <= value <= max_value:
            return value
        print(f"请输入 {min_value} 到 {max_value} 之间的数字。")


def read_optional_int(prompt: str, min_value: int, max_value: int) -> int | None:
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            print("请输入数字或留空。")
            continue
        if min_value <= value <= max_value:
            return value
        print(f"请输入 {min_value} 到 {max_value} 之间的数字，或留空。")


def wait_until(target: datetime) -> None:
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        if remaining > 1:
            time.sleep(remaining - 0.4)
        elif remaining > 0.02:
            time.sleep(remaining / 2)
        else:
            time.sleep(0.001)


def main() -> None:
    account = input("请输入账号: ").strip()
    password = getpass("请输入密码: ").strip()
    session = build_session()
    captcha = get_captcha(session)
    response = login(account, password, captcha, session)
    if response is None:
        return
    time_diff = calibration(session)
    coursedict = get_course_category(session)
    category_index = read_int("请填写选课类型序号: ", 1, len(coursedict))
    category_code = coursedict[category_index]["code"]
    courses, coursecateurl = get_course_list(session, XK_ROOT_URL + "xklx/" + category_code)
    if not courses:
        print("未查询到课程，程序结束。")
        return

    order1 = read_int("请输入第一志愿课程对应序号: ", 1, len(courses))
    order2 = read_int("请输入第二志愿课程对应序号: ", 1, len(courses))
    order3 = read_optional_int("请输入第三志愿课程对应序号(可留空): ", 1, len(courses))
    order4 = read_optional_int("请输入第四志愿课程对应序号(可留空): ", 1, len(courses))
    preferred_orders = [order1, order2, order3, order4]
    selection_time_str = input("请输入抢课时间，格式 HH:MM:SS，例如 13:00:00: ").strip()
    run_at_server = compute_run_at(selection_time_str, time_diff)
    print(f"已计划在本地时间 {run_at_server.strftime('%Y-%m-%d %H:%M:%S.%f')} 选课。")
    wait_until(run_at_server)
    select_job(preferred_orders, session, courses, coursecateurl)


if __name__ == "__main__":
    main()
