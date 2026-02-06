import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from io import BytesIO
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

import main as enroller


class EnrollerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SMU Lecture Enroller")
        self.root.geometry("980x700")
        self.root.minsize(860, 620)

        self.session = enroller.build_session()
        self.time_diff = None
        self.categories: dict[int, dict[str, str]] = {}
        self.courses: list[dict] = []
        self.coursecateurl = ""
        self.captcha_photo = None
        self.enrolling = False

        self.account_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.captcha_var = tk.StringVar()
        self.cookie_var = tk.StringVar(value="JSESSIONID=")
        self.category_var = tk.StringVar()
        self.order1_var = tk.StringVar(value="1")
        self.order2_var = tk.StringVar(value="1")
        self.order3_var = tk.StringVar(value="")
        self.order4_var = tk.StringVar(value="")
        self.time_var = tk.StringVar(value=datetime.now().strftime("%H:%M:%S"))

        self._build_ui()
        self.refresh_captcha()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.BOTH, expand=True)

        login_frame = ttk.LabelFrame(top, text="1. 登录", padding=10)
        login_frame.pack(fill=tk.X)

        ttk.Label(login_frame, text="账号").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(login_frame, textvariable=self.account_var, width=24).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(login_frame, text="密码").grid(row=0, column=2, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(login_frame, textvariable=self.password_var, show="*", width=24).grid(row=0, column=3, padx=4, pady=4)

        self.captcha_label = ttk.Label(login_frame, text="验证码")
        self.captcha_label.grid(row=0, column=4, rowspan=2, padx=8, pady=4)
        ttk.Label(login_frame, text="验证码").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(login_frame, textvariable=self.captcha_var, width=12).grid(row=1, column=1, sticky=tk.W, padx=4, pady=4)

        self.refresh_captcha_btn = ttk.Button(login_frame, text="刷新验证码", command=self.refresh_captcha)
        self.refresh_captcha_btn.grid(row=1, column=2, padx=4, pady=4, sticky=tk.W)
        self.login_btn = ttk.Button(login_frame, text="登录并加载类型", command=self.login_and_load_categories)
        self.login_btn.grid(row=1, column=3, padx=4, pady=4, sticky=tk.W)

        ttk.Label(login_frame, text="Cookie").grid(row=2, column=0, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(login_frame, textvariable=self.cookie_var, width=78).grid(
            row=2, column=1, columnspan=3, sticky=tk.W, padx=4, pady=4
        )
        self.cookie_login_btn = ttk.Button(
            login_frame,
            text="Cookie登录并加载类型",
            command=self.cookie_login_and_load_categories,
        )
        self.cookie_login_btn.grid(row=2, column=4, padx=4, pady=4, sticky=tk.W)

        self.paste_cookie_btn = ttk.Button(login_frame, text="从剪贴板粘贴Cookie", command=self.paste_cookie_from_clipboard)
        self.paste_cookie_btn.grid(row=3, column=1, padx=4, pady=4, sticky=tk.W)
        self.open_scan_btn = ttk.Button(login_frame, text="打开统一认证/扫码", command=self.open_portal_for_scan)
        self.open_scan_btn.grid(row=3, column=2, padx=4, pady=4, sticky=tk.W)
        ttk.Label(login_frame, text="支持粘贴完整Cookie或仅JSESSIONID值").grid(
            row=3, column=3, columnspan=2, sticky=tk.W, padx=4, pady=4
        )

        cfg_frame = ttk.LabelFrame(top, text="2. 课程配置", padding=10)
        cfg_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        ttk.Label(cfg_frame, text="选课类型").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.category_combo = ttk.Combobox(
            cfg_frame,
            textvariable=self.category_var,
            state="readonly",
            width=44,
        )
        self.category_combo.grid(row=0, column=1, padx=4, pady=4, sticky=tk.W)
        self.load_courses_btn = ttk.Button(cfg_frame, text="加载课程", command=self.load_courses, state=tk.DISABLED)
        self.load_courses_btn.grid(row=0, column=2, padx=4, pady=4, sticky=tk.W)

        list_frame = ttk.Frame(cfg_frame)
        list_frame.grid(row=1, column=0, columnspan=3, sticky=tk.NSEW, padx=4, pady=4)
        cfg_frame.rowconfigure(1, weight=1)
        cfg_frame.columnconfigure(1, weight=1)

        self.course_listbox = tk.Listbox(list_frame, font=("Consolas", 10), height=14)
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.course_listbox.yview)
        self.course_listbox.configure(yscrollcommand=list_scroll.set)
        self.course_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.LEFT, fill=tk.Y)

        selection_frame = ttk.Frame(cfg_frame)
        selection_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=4, pady=8)

        ttk.Label(selection_frame, text="第一志愿序号").grid(row=0, column=0, sticky=tk.W, padx=4)
        self.order1_spin = ttk.Spinbox(selection_frame, from_=1, to=1, textvariable=self.order1_var, width=7)
        self.order1_spin.grid(row=0, column=1, sticky=tk.W, padx=4)
        ttk.Label(selection_frame, text="第二志愿序号").grid(row=0, column=2, sticky=tk.W, padx=4)
        self.order2_spin = ttk.Spinbox(selection_frame, from_=1, to=1, textvariable=self.order2_var, width=7)
        self.order2_spin.grid(row=0, column=3, sticky=tk.W, padx=4)

        ttk.Button(selection_frame, text="设为第一志愿", command=lambda: self.pick_selected_course(1)).grid(
            row=0, column=4, padx=8
        )
        ttk.Button(selection_frame, text="设为第二志愿", command=lambda: self.pick_selected_course(2)).grid(
            row=0, column=5, padx=4
        )
        ttk.Label(selection_frame, text="第三志愿序号(可空)").grid(row=1, column=0, sticky=tk.W, padx=4, pady=(6, 0))
        ttk.Entry(selection_frame, textvariable=self.order3_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=4, pady=(6, 0))
        ttk.Label(selection_frame, text="第四志愿序号(可空)").grid(row=1, column=2, sticky=tk.W, padx=4, pady=(6, 0))
        ttk.Entry(selection_frame, textvariable=self.order4_var, width=8).grid(row=1, column=3, sticky=tk.W, padx=4, pady=(6, 0))
        ttk.Button(selection_frame, text="设为第三志愿", command=lambda: self.pick_selected_course(3)).grid(
            row=1, column=4, padx=8, pady=(6, 0)
        )
        ttk.Button(selection_frame, text="设为第四志愿", command=lambda: self.pick_selected_course(4)).grid(
            row=1, column=5, padx=4, pady=(6, 0)
        )

        run_frame = ttk.LabelFrame(top, text="3. 开始抢课", padding=10)
        run_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(run_frame, text="抢课时间 (HH:MM:SS)").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        ttk.Entry(run_frame, textvariable=self.time_var, width=16).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
        self.start_btn = ttk.Button(run_frame, text="开始抢课", command=self.start_enroll, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=2, sticky=tk.W, padx=8, pady=4)

        log_frame = ttk.LabelFrame(top, text="日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = tk.Text(log_frame, height=12, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10))
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.LEFT, fill=tk.Y)

    def run_in_thread(self, target) -> None:
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        def append() -> None:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        self.root.after(0, append)

    def refresh_captcha(self) -> None:
        self.refresh_captcha_btn.configure(state=tk.DISABLED)

        def task() -> None:
            try:
                data = enroller.fetch_captcha_bytes(self.session)
            except Exception as exc:  # noqa: BLE001
                self.log(f"获取验证码失败: {exc}")
                data = b""

            def update_image() -> None:
                if data:
                    image = Image.open(BytesIO(data))
                    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                    image = image.resize((120, 44), resample)
                    self.captcha_photo = ImageTk.PhotoImage(image)
                    self.captcha_label.configure(image=self.captcha_photo, text="")
                self.refresh_captcha_btn.configure(state=tk.NORMAL)

            self.root.after(0, update_image)

        self.run_in_thread(task)

    def paste_cookie_from_clipboard(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showerror("剪贴板为空", "没有读取到剪贴板文本。")
            return
        cookie_text = text.strip()
        if not cookie_text:
            messagebox.showerror("剪贴板为空", "没有读取到有效 Cookie 文本。")
            return
        if "=" not in cookie_text and ";" not in cookie_text:
            cookie_text = f"JSESSIONID={cookie_text}"
            self.log("检测到 Cookie 纯值，已自动补全为 JSESSIONID=...")
        self.cookie_var.set(cookie_text)
        self.log("已从剪贴板填充 Cookie。")

    def open_portal_for_scan(self) -> None:
        webbrowser.open(enroller.PORTAL_URL)
        self.log("已打开统一认证页面，请在浏览器完成扫码/登录后复制 Cookie。")

    def login_and_load_categories(self) -> None:
        account = self.account_var.get().strip()
        password = self.password_var.get().strip()
        captcha = self.captcha_var.get().strip()
        if not account or not password or not captcha:
            messagebox.showerror("输入不完整", "请填写账号、密码和验证码。")
            return

        self.login_btn.configure(state=tk.DISABLED)
        self.cookie_login_btn.configure(state=tk.DISABLED)
        self.load_courses_btn.configure(state=tk.DISABLED)
        self.start_btn.configure(state=tk.DISABLED)

        def task() -> None:
            try:
                response = enroller.login(account, password, captcha, self.session, logger=self.log)
                if response is None:
                    self.log("登录失败，请刷新验证码重试。")
                    self.root.after(0, self.refresh_captcha)
                    return

                self.load_categories_after_auth()
            except Exception as exc:  # noqa: BLE001
                self.log(f"登录或加载类型失败: {exc}")
            finally:
                self.root.after(
                    0,
                    lambda: (
                        self.login_btn.configure(state=tk.NORMAL),
                        self.cookie_login_btn.configure(state=tk.NORMAL),
                    ),
                )

        self.run_in_thread(task)

    def cookie_login_and_load_categories(self) -> None:
        cookie_text = self.cookie_var.get().strip()
        if not cookie_text:
            messagebox.showerror("输入不完整", "请先粘贴浏览器 Cookie。")
            return

        self.login_btn.configure(state=tk.DISABLED)
        self.cookie_login_btn.configure(state=tk.DISABLED)
        self.load_courses_btn.configure(state=tk.DISABLED)
        self.start_btn.configure(state=tk.DISABLED)

        def task() -> None:
            try:
                ok = enroller.login_with_cookie(cookie_text, self.session, logger=self.log)
                if not ok:
                    return
                self.load_categories_after_auth()
            except Exception as exc:  # noqa: BLE001
                self.log(f"Cookie 登录失败: {exc}")
            finally:
                self.root.after(
                    0,
                    lambda: (
                        self.login_btn.configure(state=tk.NORMAL),
                        self.cookie_login_btn.configure(state=tk.NORMAL),
                    ),
                )

        self.run_in_thread(task)

    def load_categories_after_auth(self) -> None:
        self.time_diff = enroller.calibration(self.session, logger=self.log)
        categories = enroller.get_course_category(self.session, logger=self.log)
        self.categories = categories
        values = [f"{idx}. {meta['title']}" for idx, meta in categories.items()]

        def update_categories() -> None:
            self.category_combo["values"] = values
            if values:
                self.category_combo.current(0)
            self.load_courses_btn.configure(state=tk.NORMAL)
            self.log("请选择类型并点击“加载课程”。")

        self.root.after(0, update_categories)

    def _selected_category_index(self) -> int | None:
        value = self.category_var.get().strip()
        if not value:
            return None
        try:
            return int(value.split(".", 1)[0])
        except ValueError:
            return None

    def load_courses(self) -> None:
        category_index = self._selected_category_index()
        if category_index is None or category_index not in self.categories:
            messagebox.showerror("未选择类型", "请先选择一个有效的选课类型。")
            return

        self.load_courses_btn.configure(state=tk.DISABLED)
        self.start_btn.configure(state=tk.DISABLED)

        def task() -> None:
            try:
                category_code = self.categories[category_index]["code"]
                courses, coursecateurl = enroller.get_course_list(
                    self.session,
                    enroller.XK_ROOT_URL + "xklx/" + category_code,
                    logger=self.log,
                )
                self.courses = courses
                self.coursecateurl = coursecateurl

                def update_courses() -> None:
                    self.course_listbox.delete(0, tk.END)
                    for idx, course in enumerate(courses, start=1):
                        title = course.get("kcmc", "")
                        teacher = course.get("teaxm", "")
                        self.course_listbox.insert(tk.END, f"{idx:>3}. {title} {teacher}")
                    if courses:
                        course_count = len(courses)
                        self.order1_spin.configure(from_=1, to=course_count)
                        self.order2_spin.configure(from_=1, to=course_count)
                        self.order1_var.set("1")
                        self.order2_var.set("1" if course_count == 1 else "2")
                        self.order3_var.set("")
                        self.order4_var.set("")
                        self.start_btn.configure(state=tk.NORMAL)
                        self.log("课程加载完成，设置志愿后可开始抢课。")
                    else:
                        self.log("未查询到课程。")

                self.root.after(0, update_courses)
            except Exception as exc:  # noqa: BLE001
                self.log(f"加载课程失败: {exc}")
            finally:
                self.root.after(0, lambda: self.load_courses_btn.configure(state=tk.NORMAL))

        self.run_in_thread(task)

    def pick_selected_course(self, order_slot: int) -> None:
        selected = self.course_listbox.curselection()
        if not selected:
            return
        index = selected[0] + 1
        if order_slot == 1:
            self.order1_var.set(str(index))
        elif order_slot == 2:
            self.order2_var.set(str(index))
        elif order_slot == 3:
            self.order3_var.set(str(index))
        elif order_slot == 4:
            self.order4_var.set(str(index))

    def parse_optional_order(self, raw: str, course_count: int) -> int | None:
        value = raw.strip()
        if not value:
            return None
        order = int(value)
        if not (1 <= order <= course_count):
            raise ValueError("志愿序号超出课程范围")
        return order

    def start_enroll(self) -> None:
        if self.enrolling:
            return
        if not self.courses or not self.coursecateurl or self.time_diff is None:
            messagebox.showerror("状态不足", "请先登录并加载课程。")
            return
        try:
            order1 = int(self.order1_var.get().strip())
            order2 = int(self.order2_var.get().strip())
            order3 = self.parse_optional_order(self.order3_var.get(), len(self.courses))
            order4 = self.parse_optional_order(self.order4_var.get(), len(self.courses))
        except ValueError:
            messagebox.showerror("输入错误", "前两志愿必须为数字，第三/第四志愿可留空或填数字。")
            return
        if not (1 <= order1 <= len(self.courses)) or not (1 <= order2 <= len(self.courses)):
            messagebox.showerror("输入错误", "志愿序号超出课程范围。")
            return
        preferred_orders = [order1, order2, order3, order4]

        selection_time_str = self.time_var.get().strip()
        try:
            run_at = enroller.compute_run_at(selection_time_str, self.time_diff)
        except ValueError:
            messagebox.showerror("时间格式错误", "请使用 HH:MM:SS，例如 13:00:00。")
            return

        self.enrolling = True
        self.start_btn.configure(state=tk.DISABLED)
        self.log(f"已计划在本地时间 {run_at.strftime('%Y-%m-%d %H:%M:%S.%f')} 开始抢课。")

        def task() -> None:
            try:
                enroller.wait_until(run_at)
                enroller.select_job(preferred_orders, self.session, self.courses, self.coursecateurl, logger=self.log)
            except Exception as exc:  # noqa: BLE001
                self.log(f"抢课流程异常: {exc}")
            finally:
                self.enrolling = False
                self.root.after(0, lambda: self.start_btn.configure(state=tk.NORMAL))

        self.run_in_thread(task)


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    EnrollerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
