import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import time
import csv
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


class LoadTesterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Website Capacity Tester")
        self.root.geometry("950x700")

        self.stop_event = threading.Event()
        self.result_queue = queue.Queue()
        self.results = []

        self.create_gui()
        self.root.after(100, self.process_queue)

    def create_gui(self):
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="WEBSITE CAPACITY TESTER",
            font=("Arial", 18, "bold")
        ).pack(pady=(0, 15))

        config = ttk.LabelFrame(frame, text="Test Configuration", padding=10)
        config.pack(fill="x")

        ttk.Label(config, text="Website URL:").grid(row=0, column=0, sticky="w")
        self.url_entry = ttk.Entry(config, width=60)
        self.url_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5)
        self.url_entry.insert(0, "https://example.com")

        ttk.Label(config, text="Start users:").grid(row=1, column=0, sticky="w")
        self.start_users = ttk.Entry(config, width=10)
        self.start_users.grid(row=1, column=1, sticky="w")
        self.start_users.insert(0, "10")

        ttk.Label(config, text="Maximum users:").grid(row=1, column=2, sticky="w")
        self.max_users = ttk.Entry(config, width=10)
        self.max_users.grid(row=1, column=3, sticky="w")
        self.max_users.insert(0, "100")

        ttk.Label(config, text="Step:").grid(row=2, column=0, sticky="w")
        self.step_users = ttk.Entry(config, width=10)
        self.step_users.grid(row=2, column=1, sticky="w")
        self.step_users.insert(0, "10")

        ttk.Label(config, text="Requests/user:").grid(row=2, column=2, sticky="w")
        self.requests_user = ttk.Entry(config, width=10)
        self.requests_user.grid(row=2, column=3, sticky="w")
        self.requests_user.insert(0, "2")

        ttk.Label(config, text="Timeout (seconds):").grid(row=3, column=0, sticky="w")
        self.timeout = ttk.Entry(config, width=10)
        self.timeout.grid(row=3, column=1, sticky="w")
        self.timeout.insert(0, "10")

        ttk.Label(config, text="Maximum acceptable error %:").grid(
            row=3, column=2, sticky="w"
        )
        self.max_error = ttk.Entry(config, width=10)
        self.max_error.grid(row=3, column=3, sticky="w")
        self.max_error.insert(0, "5")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=12)

        self.start_button = ttk.Button(
            buttons,
            text="START TEST",
            command=self.start_test
        )
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(
            buttons,
            text="STOP",
            command=self.stop_test,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)

        ttk.Button(
            buttons,
            text="Export CSV",
            command=self.export_csv
        ).pack(side="left", padx=5)

        status = ttk.LabelFrame(frame, text="Current Test", padding=10)
        status.pack(fill="x")

        self.current_users = tk.StringVar(value="0")
        self.completed = tk.StringVar(value="0")
        self.successful = tk.StringVar(value="0")
        self.failed = tk.StringVar(value="0")
        self.error_rate = tk.StringVar(value="0%")
        self.average_time = tk.StringVar(value="0 ms")
        self.p95_time = tk.StringVar(value="0 ms")
        self.test_status = tk.StringVar(value="READY")

        rows = [
            ("Current users:", self.current_users),
            ("Requests completed:", self.completed),
            ("Successful:", self.successful),
            ("Failed:", self.failed),
            ("Error rate:", self.error_rate),
            ("Average response:", self.average_time),
            ("95th percentile:", self.p95_time),
            ("Status:", self.test_status),
        ]

        for i, (label, variable) in enumerate(rows):
            ttk.Label(status, text=label).grid(
                row=i // 2,
                column=(i % 2) * 2,
                sticky="w",
                padx=5,
                pady=3
            )

            ttk.Label(
                status,
                textvariable=variable,
                font=("Arial", 10, "bold")
            ).grid(
                row=i // 2,
                column=(i % 2) * 2 + 1,
                sticky="w",
                padx=5,
                pady=3
            )

        result_frame = ttk.LabelFrame(frame, text="Load Results", padding=5)
        result_frame.pack(fill="both", expand=True, pady=10)

        columns = (
            "users",
            "requests",
            "success",
            "failed",
            "error",
            "avg",
            "p95",
            "status"
        )

        self.tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings"
        )

        headings = {
            "users": "Users",
            "requests": "Requests",
            "success": "Success",
            "failed": "Failed",
            "error": "Error %",
            "avg": "Avg ms",
            "p95": "P95 ms",
            "status": "Result"
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=90, anchor="center")

        scrollbar = ttk.Scrollbar(
            result_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.progress = ttk.Progressbar(
            frame,
            mode="determinate"
        )
        self.progress.pack(fill="x")

    def start_test(self):
        try:
            start = int(self.start_users.get())
            maximum = int(self.max_users.get())
            step = int(self.step_users.get())

            if start <= 0 or maximum < start or step <= 0:
                raise ValueError

        except ValueError:
            messagebox.showerror(
                "Invalid configuration",
                "Please enter valid user numbers."
            )
            return

        url = self.url_entry.get().strip()

        if not url.startswith(("http://", "https://")):
            messagebox.showerror(
                "Invalid URL",
                "URL must start with http:// or https://"
            )
            return

        self.results.clear()
        self.stop_event.clear()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        self.test_status.set("STARTING")

        thread = threading.Thread(
            target=self.run_test,
            args=(url, start, maximum, step),
            daemon=True
        )

        thread.start()

    def stop_test(self):
        self.stop_event.set()
        self.test_status.set("STOPPING...")

    def run_test(self, url, start, maximum, step):
        try:
            requests_per_user = int(self.requests_user.get())
            timeout = float(self.timeout.get())
            allowed_error = float(self.max_error.get())

            total_steps = ((maximum - start) // step) + 1

            self.result_queue.put(
                ("progress_max", total_steps)
            )

            users = start

            while users <= maximum:

                if self.stop_event.is_set():
                    break

                self.result_queue.put(
                    ("users", users)
                )

                result = self.run_load(
                    url,
                    users,
                    requests_per_user,
                    timeout
                )

                error_rate = (
                    result["failed"] / result["requests"] * 100
                    if result["requests"]
                    else 100
                )

                if error_rate >= allowed_error:
                    status = "FAIL"
                elif result["p95"] >= timeout * 1000:
                    status = "DEGRADED"
                else:
                    status = "PASS"

                result["users"] = users
                result["error_rate"] = error_rate
                result["status"] = status

                self.results.append(result)

                self.result_queue.put(
                    ("result", result)
                )

                # Stop automatically once the configured
                # failure threshold has been reached.
                if status == "FAIL":
                    break

                users += step

            if self.stop_event.is_set():
                final_status = "STOPPED"
            elif self.results:
                last = self.results[-1]

                if last["status"] == "FAIL":
                    final_status = "FAIL"
                elif last["status"] == "DEGRADED":
                    final_status = "DEGRADED"
                else:
                    final_status = "PASS"
            else:
                final_status = "NO TEST"

            self.result_queue.put(
                ("finished", final_status)
            )

        except Exception as e:
            self.result_queue.put(
                ("error", str(e))
            )

    def run_load(self, url, users, requests_per_user, timeout):

        response_times = []
        successful = 0
        failed = 0
        completed = 0

        def request_task():
            nonlocal successful
            nonlocal failed
            nonlocal completed

            local_times = []
            local_success = 0
            local_failed = 0

            for _ in range(requests_per_user):

                if self.stop_event.is_set():
                    break

                start_time = time.perf_counter()

                try:
                    response = requests.get(
                        url,
                        timeout=timeout
                    )

                    elapsed = (
                        time.perf_counter() - start_time
                    ) * 1000

                    local_times.append(elapsed)

                    if 200 <= response.status_code < 400:
                        local_success += 1
                    else:
                        local_failed += 1

                except requests.RequestException:
                    elapsed = (
                        time.perf_counter() - start_time
                    ) * 1000

                    local_times.append(elapsed)
                    local_failed += 1

            return (
                local_times,
                local_success,
                local_failed
            )

        with ThreadPoolExecutor(
            max_workers=users
        ) as executor:

            futures = [
                executor.submit(request_task)
                for _ in range(users)
            ]

            for future in as_completed(futures):

                if self.stop_event.is_set():
                    break

                times, success, failures = future.result()

                response_times.extend(times)
                successful += success
                failed += failures

                completed = successful + failed

                self.result_queue.put(
                    ("live", {
                        "completed": completed,
                        "success": successful,
                        "failed": failed,
                        "times": response_times
                    })
                )

        if response_times:
            average = statistics.mean(response_times)

            sorted_times = sorted(response_times)

            index = int(
                len(sorted_times) * 0.95
            )

            index = min(
                index,
                len(sorted_times) - 1
            )

            p95 = sorted_times[index]

        else:
            average = 0
            p95 = 0

        return {
            "requests": successful + failed,
            "success": successful,
            "failed": failed,
            "avg": average,
            "p95": p95
        }

    def process_queue(self):

        try:
            while True:

                message = self.result_queue.get_nowait()

                kind = message[0]
                data = message[1]

                if kind == "progress_max":
                    self.progress["maximum"] = data
                    self.progress["value"] = 0

                elif kind == "users":
                    self.current_users.set(str(data))
                    self.test_status.set(
                        f"TESTING — {data} users"
                    )

                elif kind == "live":

                    self.completed.set(
                        str(data["completed"])
                    )

                    self.successful.set(
                        str(data["success"])
                    )

                    self.failed.set(
                        str(data["failed"])
                    )

                    total = data["completed"]

                    if total:
                        error = (
                            data["failed"] / total * 100
                        )
                    else:
                        error = 0

                    self.error_rate.set(
                        f"{error:.2f}%"
                    )

                    if data["times"]:
                        avg = statistics.mean(
                            data["times"]
                        )

                        self.average_time.set(
                            f"{avg:.0f} ms"
                        )

                elif kind == "result":

                    result = data

                    self.tree.insert(
                        "",
                        "end",
                        values=(
                            result["users"],
                            result["requests"],
                            result["success"],
                            result["failed"],
                            f"{result['error_rate']:.2f}",
                            f"{result['avg']:.0f}",
                            f"{result['p95']:.0f}",
                            result["status"]
                        )
                    )

                    self.p95_time.set(
                        f"{result['p95']:.0f} ms"
                    )

                    self.progress["value"] += 1

                elif kind == "finished":

                    self.test_status.set(
                        f"TEST COMPLETE — {data}"
                    )

                    self.start_button.config(
                        state="normal"
                    )

                    self.stop_button.config(
                        state="disabled"
                    )

                    if data == "FAIL":
                        messagebox.showwarning(
                            "Capacity limit detected",
                            "The configured failure threshold "
                            "was reached."
                        )

                elif kind == "error":

                    self.test_status.set("ERROR")

                    self.start_button.config(
                        state="normal"
                    )

                    self.stop_button.config(
                        state="disabled"
                    )

                    messagebox.showerror(
                        "Test error",
                        data
                    )

        except queue.Empty:
            pass

        self.root.after(
            100,
            self.process_queue
        )

    def export_csv(self):

        if not self.results:
            messagebox.showinfo(
                "No data",
                "Run a test before exporting."
            )
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV files", "*.csv")
            ]
        )

        if not filename:
            return

        fields = [
            "users",
            "requests",
            "success",
            "failed",
            "error_rate",
            "avg",
            "p95",
            "status"
        ]

        with open(
            filename,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fields
            )

            writer.writeheader()

            for result in self.results:
                writer.writerow(result)

        messagebox.showinfo(
            "Export complete",
            f"Report saved to:\n{filename}"
        )


if __name__ == "__main__":
    root = tk.Tk()

    app = LoadTesterGUI(root)

    root.mainloop()
