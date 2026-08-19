#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, cast

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import config as app_config
from scripts.converters.utils import get_localized_text
from scripts.services import ConversionService, configure_logging, get_logger
from scripts.typing_contracts import ConverterModuleName, ConverterName

logger = get_logger(__name__)

RowData = dict[str, str | Path | None]
VALID_CONVERTER_NAMES: tuple[ConverterName, ...] = (
    "keytrade",
    "amex",
    "argenta",
    "mastercard",
)
VALID_MODULE_NAMES: tuple[ConverterModuleName, ...] = (
    "keytrade_csv",
    "amex_csv",
    "amex_xlsx",
    "argenta_xlsx",
    "mastercard_pdf",
)


class ConversionGuiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(get_localized_text("gui_title"))
        self.root.geometry("1360x780")
        self.root.minsize(1180, 620)
        self.root.configure(bg="#edf2f7")
        self.dark_mode = True
        self.service = ConversionService()
        self.rows: dict[str, RowData] = {}
        self._drag_drop_enabled = False
        self.summary_cards: dict[str, tk.Label] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self.previous_report_stats: dict[str, Any] = {}
        self.sidebar_actions: dict[str, list[tuple[str, Any]]] = {}
        self.header: tk.Frame | None = None
        self.content: tk.Frame | None = None
        self.status_panel: tk.Frame | None = None
        self.status_icon: tk.Label | None = None
        self.status_text_label: tk.Label | None = None
        self.tree: ttk.Treeview | None = None
        self.row_context_menu: tk.Menu | None = None
        self.mode_toggle: tk.Button | None = None
        self.yscroll: ttk.Scrollbar | None = None
        self.xscroll: ttk.Scrollbar | None = None

        self._build_ui()
        self._apply_theme()
        self._setup_drag_and_drop()

    def _get_tree(self) -> ttk.Treeview:
        if self.tree is None:
            raise RuntimeError("Treeview has not been initialized")
        return self.tree

    def _bind_summary_card_click(self, widget: tk.Widget, key: str) -> None:
        def handler(_event: Any) -> None:
            self._handle_summary_card_click(key)

        widget.bind("<Button-1>", handler)

    def _parse_converter_name(self, value: object) -> ConverterName | None:
        if value in VALID_CONVERTER_NAMES:
            return value
        return None

    def _parse_module_name(self, value: object) -> ConverterModuleName | None:
        if value in VALID_MODULE_NAMES:
            return value
        return None

    def _apply_theme(self) -> None:
        style = ttk.Style(self.root)
        theme_names = style.theme_names()
        if "clam" in theme_names:
            style.theme_use("clam")

        if self.dark_mode:
            root_bg = "#0b1020"
            app_bg = "#111827"
            panel_bg = "#0f172a"
            card_bg = "#111827"
            subtle_bg = "#1e293b"
            text = "#e2e8f0"
            muted = "#94a3b8"
            accent = "#60a5fa"
            input_bg = "#0f172a"
        else:
            root_bg = "#edf2f7"
            app_bg = "#f8fafc"
            panel_bg = "#ffffff"
            card_bg = "#ffffff"
            subtle_bg = "#eef2ff"
            text = "#0f172a"
            muted = "#475569"
            accent = "#2563eb"
            input_bg = "#ffffff"

        self.root.configure(bg=root_bg)
        if hasattr(self, "menubar"):
            self.menubar.configure(bg=app_bg, fg=text)

        if self.header is not None:
            self.header.configure(bg="#d4d0c8")
        if self.content is not None:
            self.content.configure(bg="#d4d0c8")
        if self.status_panel is not None:
            self.status_panel.configure(bg="#f3f4f6")
        if self.status_icon is not None:
            self.status_icon.configure(bg="#f3f4f6", fg=accent)
        if hasattr(self, "status_var"):
            self._update_status(self.status_var.get(), tone="info")

        for button in self.nav_buttons.values():
            button.configure(
                bg="#101827" if self.dark_mode else "#f8fafc",
                fg="#e2e8f0" if self.dark_mode else "#0f172a",
            )

        style.configure("Card.TFrame", background=card_bg)
        style.configure(
            "Treeview",
            rowheight=26,
            font=("Segoe UI", 9),
            background=input_bg,
            fieldbackground=input_bg,
            foreground=text,
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=subtle_bg,
            foreground=text,
        )
        style.map(
            "Treeview",
            background=[("selected", accent)],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Status.TLabel",
            background=panel_bg,
            foreground=muted,
            font=("Segoe UI", 9),
        )

        if self.tree is not None:
            self.tree.tag_configure(
                "status_ok", background="#dcfce7", foreground="#166534"
            )
            self.tree.tag_configure(
                "status_failed", background="#fee2e2", foreground="#991b1b"
            )
            self.tree.tag_configure(
                "status_skipped", background="#fef3c7", foreground="#92400e"
            )
            self.tree.tag_configure(
                "status_ready", background="#dbeafe", foreground="#1d4ed8"
            )
            self.tree.tag_configure(
                "status_default", background="#f3f4f6", foreground="#374151"
            )

        if self.mode_toggle is not None:
            self.mode_toggle.configure(
                text="☀️ Light mode" if self.dark_mode else "🌙 Dark mode",
                bg="#101827" if self.dark_mode else "#f8fafc",
                fg="#f8fafc" if self.dark_mode else "#0f172a",
            )

    def _apply_display_mode(self, value: str | None = None) -> None:
        normalized = str(value or "").strip().casefold()
        if normalized in {"light", "clair"}:
            self.dark_mode = False
        elif normalized in {"dark", "sombre"}:
            self.dark_mode = True
        else:
            self.dark_mode = not self.dark_mode
        self._apply_theme()
        selected = (
            get_localized_text("dark_label")
            if self.dark_mode
            else get_localized_text("light_label")
        )
        self._update_status(
            get_localized_text("display_mode_status", selected=selected)
        )

    def _choose_display_mode(self) -> None:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#111827",
            fg="#e2e8f0",
            activebackground="#1f2937",
            activeforeground="#ffffff",
            bd=0,
            relief="flat",
            font=("Segoe UI", 9),
        )
        menu.add_command(
            label=get_localized_text("light_label"),
            command=lambda: self._apply_display_mode("light"),
            foreground="#e2e8f0",
            background="#111827",
            activebackground="#1f2937",
            activeforeground="#ffffff",
        )
        menu.add_separator()
        menu.add_command(
            label=get_localized_text("dark_label"),
            command=lambda: self._apply_display_mode("dark"),
            foreground="#e2e8f0",
            background="#111827",
            activebackground="#1f2937",
            activeforeground="#ffffff",
        )

        target = self.nav_buttons.get("display_mode")
        if target is not None:
            x = target.winfo_rootx() + 8
            y = target.winfo_rooty() + target.winfo_height() + 4
            menu.post(x, y)
        else:
            x = self.root.winfo_rootx() + 180
            y = self.root.winfo_rooty() + 150
            menu.post(x, y)

    def _apply_output_language(self, value: str | None = None) -> None:
        normalized = str(
            value or getattr(app_config, "OUTPUT_LANGUAGE", "english") or "english"
        )
        clean = normalized.strip().casefold()
        language = (
            "french"
            if clean in {"fr", "fra", "france", "french", "français"}
            else "english"
        )
        app_config.OUTPUT_LANGUAGE = language
        os.environ["HBCONV_OUTPUT_LANGUAGE"] = language
        if hasattr(self, "output_language_var"):
            self.output_language_var.set(
                get_localized_text("french_label")
                if language == "french"
                else get_localized_text("english_label")
            )
        self.root.title(get_localized_text("gui_title"))
        self._update_status(
            get_localized_text(
                "output_language_status",
                selected=(
                    self.output_language_var.get()
                    if hasattr(self, "output_language_var")
                    else language
                ),
            )
        )

    def _choose_output_language(self) -> None:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#111827",
            fg="#e2e8f0",
            activebackground="#1f2937",
            activeforeground="#ffffff",
            bd=0,
            relief="flat",
            font=("Segoe UI", 9),
        )
        menu.add_command(
            label="English",
            command=lambda: self._apply_output_language("English"),
            foreground="#e2e8f0",
            background="#111827",
            activebackground="#1f2937",
            activeforeground="#ffffff",
        )
        menu.add_separator()
        menu.add_command(
            label="Français",
            command=lambda: self._apply_output_language("Français"),
            foreground="#e2e8f0",
            background="#111827",
            activebackground="#1f2937",
            activeforeground="#ffffff",
        )

        target = self.nav_buttons.get("language")
        if target is not None:
            x = target.winfo_rootx() + 8
            y = target.winfo_rooty() + target.winfo_height() + 4
            menu.post(x, y)
        else:
            x = self.root.winfo_rootx() + 180
            y = self.root.winfo_rooty() + 150
            menu.post(x, y)

    def _build_sidebar_section(
        self, sidebar: tk.Widget, title: str, action_specs: list[tuple[str, Any]]
    ) -> None:
        section = tk.LabelFrame(
            sidebar,
            text=title,
            bg="#d4d0c8",
            fg="#1f1f1f",
            padx=8,
            pady=8,
            highlightbackground="#7a7a7a",
            highlightthickness=1,
            bd=1,
            font=("Segoe UI", 9, "bold"),
        )
        section.pack(fill="x", padx=8, pady=(6, 8))
        section.configure(relief="groove")
        self.sidebar_actions[title.lower()] = action_specs

        for label, command in action_specs:
            button = tk.Button(
                section,
                text=label,
                command=command,
                bg="#f0f0f0",
                fg="#1f1f1f",
                bd=2,
                relief="raised",
                highlightbackground="#8a8a8a",
                highlightthickness=1,
                activebackground="#d9d9d9",
                activeforeground="#000000",
                padx=12,
                pady=9,
                anchor="w",
                justify="left",
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
            )
            button.pack(fill="x", pady=2, ipady=2)
            self.nav_buttons[label.lower().replace(" ", "_")] = button

    def _build_ui(self) -> None:
        is_french = (
            getattr(app_config, "OUTPUT_LANGUAGE", "english").lower().startswith("fr")
        )
        self.output_language_var = tk.StringVar(
            value=(
                get_localized_text("french_label")
                if is_french
                else get_localized_text("english_label")
            )
        )

        root_widget = tk.Frame(self.root, bg="#d4d0c8")
        root_widget.pack(fill="both", expand=True)
        self.content = root_widget

        toolbar = tk.Frame(root_widget, bg="#d4d0c8", padx=6, pady=6)
        toolbar.pack(fill="x")

        classic_bar = tk.Frame(toolbar, bg="#000000")
        classic_bar.pack(fill="x")

        actions = [
            ("Files", self.add_files),
            ("Add Folder", self.add_folder),
            ("Remove Selected", self.remove_selected),
            ("Clean File List", self.clear_rows),
            ("Convert Selected", self.convert_selected),
            ("Convert All", self.convert_all),
            ("Retry Failed", self.retry_failed),
            ("Open Output Folder", self.open_output_folder),
            (get_localized_text("menu_language"), self._choose_output_language),
            (get_localized_text("menu_display_mode"), self._choose_display_mode),
            ("Exit", self.exit_app),
        ]

        for label, command in actions:
            button_frame = tk.Frame(classic_bar, bg="#7b7b7b", padx=1, pady=1)
            button_frame.pack(
                side="right" if label == "Exit" else "left",
                padx=(0, 6),
                pady=2,
            )

            btn = tk.Button(
                button_frame,
                text=label,
                command=command,
                bg="#0b2447",
                fg="#ffffff",
                bd=0,
                relief="flat",
                activebackground="#163d6b",
                activeforeground="#ffffff",
                padx=12,
                pady=7,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
            )
            btn.pack()
            self.nav_buttons[label.lower().replace(" ", "_")] = btn

        header = tk.Frame(root_widget, bg="#d4d0c8", height=86)
        header.pack(fill="x", padx=6, pady=(0, 6))
        header.pack_propagate(False)
        self.header = header

        title = tk.Label(
            header,
            text="HomeBank Converter",
            font=("Segoe UI", 20, "bold"),
            fg="#1f1f1f",
            bg="#d4d0c8",
            anchor="w",
        )
        title.place(x=12, y=8)

        subtitle = tk.Label(
            header,
            text="Processing, audit, and report management",
            font=("Segoe UI", 9),
            fg="#4c4c4c",
            bg="#d4d0c8",
            anchor="w",
        )
        subtitle.place(x=14, y=46)

        body = tk.Frame(root_widget, bg="#d4d0c8")
        body.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        summary_bar = tk.Frame(body, bg="#d4d0c8", padx=8, pady=4)
        summary_bar.pack(fill="x", pady=(6, 8))
        palette = [
            ("files", "Files", "0", "#dfe9ff", "#1d4ed8"),
            ("ready", "Ready", "0", "#e0f2fe", "#0284c7"),
            ("ok", get_localized_text("summary_ok_report"), "0", "#dcfce7", "#16a34a"),
            ("failed", "Failed", "0", "#fee2e2", "#dc2626"),
            ("skipped", "Skipped", "0", "#fef3c7", "#d97706"),
        ]
        for index, (key, label, value, bg, accent) in enumerate(palette):
            card = tk.Frame(
                summary_bar,
                bg=bg,
                padx=10,
                pady=8,
                highlightbackground=accent,
                highlightthickness=1,
            )
            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0, 8 if index < len(palette) - 1 else 0),
            )
            title = tk.Label(
                card, text=label, font=("Segoe UI", 9, "bold"), fg=accent, bg=bg
            )
            title.pack(anchor="w")
            value_label = tk.Label(
                card,
                text=value,
                font=("Segoe UI", 14, "bold"),
                fg="#0f172a",
                bg=bg,
            )
            value_label.pack(anchor="w", pady=(2, 0))
            self.summary_cards[key] = value_label
            if key in {"ok", "failed"}:
                self._bind_summary_card_click(card, key)
                self._bind_summary_card_click(title, key)
                self._bind_summary_card_click(value_label, key)
            summary_bar.grid_columnconfigure(index, weight=1)
        for column_index in range(len(palette)):
            summary_bar.grid_columnconfigure(column_index, weight=1)

        self._refresh_summary_cards()

        table_frame = ttk.Frame(body, padding=(8, 8, 8, 6), style="Card.TFrame")
        table_frame.pack(fill="both", expand=True)

        columns = ("file", "detected", "module", "status", "output", "report", "error")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=9)
        self.tree = tree
        tree.heading("file", text=get_localized_text("column_file"))
        tree.heading("detected", text=get_localized_text("column_detected"))
        tree.heading("module", text=get_localized_text("column_module"))
        tree.heading("status", text=get_localized_text("column_status"))
        tree.heading("output", text=get_localized_text("column_output"))
        tree.heading("report", text=get_localized_text("column_report"))
        tree.heading("error", text=get_localized_text("column_error"))

        tree.column("file", width=230, anchor="w")
        tree.column("detected", width=90, anchor="w")
        tree.column("module", width=130, anchor="w")
        tree.column("status", width=75, anchor="w")
        tree.column("output", width=240, anchor="w")
        tree.column("report", width=240, anchor="w")
        tree.column("error", width=220, anchor="w")

        tree.tag_configure("status_ok", background="#0c3d2a", foreground="#dfffe9")
        tree.tag_configure("status_failed", background="#4a1f1f", foreground="#ffe4e4")
        tree.tag_configure("status_skipped", background="#5d4a1a", foreground="#fff1b8")
        tree.tag_configure("status_ready", background="#1d3557", foreground="#dfeeff")
        tree.tag_configure("status_default", background="#0f172a", foreground="#e2e8f0")

        style = ttk.Style(self.root)
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#101827",
            foreground="#e2e8f0",
        )
        style.configure(
            "Treeview",
            font=("Consolas", 9),
            rowheight=22,
            background="#071421",
            fieldbackground="#071421",
            foreground="#dfeaf7",
        )

        self.yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        self.xscroll = ttk.Scrollbar(
            table_frame, orient="horizontal", command=tree.xview
        )
        tree.configure(yscrollcommand=self.yscroll.set, xscrollcommand=self.xscroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        self.yscroll.grid(row=0, column=1, sticky="ns")
        self.xscroll.grid(row=1, column=0, sticky="ew")
        self._update_table_scrollbar()

        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        progress_frame = ttk.Frame(body, padding=(8, 0, 8, 6), style="Card.TFrame")
        progress_frame.pack(fill="x")
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", length=600)
        self.progress.pack(fill="x", side="left", expand=True)
        self.progress_label_var = tk.StringVar(value="0/0")
        ttk.Label(
            progress_frame, textvariable=self.progress_label_var, width=10, anchor="e"
        ).pack(side="right", padx=(8, 0))

        self.status_var = tk.StringVar(
            value=get_localized_text("status_no_files_loaded")
        )
        status_panel = tk.Frame(body, bg="#0f172a", padx=12, pady=8)
        status_panel.pack(fill="x", padx=8, pady=(0, 8))
        self.status_panel = status_panel
        status_icon = tk.Label(
            status_panel,
            text="●",
            fg="#2563eb",
            bg="#0f172a",
            font=("Segoe UI", 11, "bold"),
        )
        status_icon.pack(side="left")
        self.status_icon = status_icon
        self.status_text_label = tk.Label(
            status_panel,
            textvariable=self.status_var,
            bg="#f3f4f6",
            fg="#1f2937",
            anchor="w",
            justify="left",
            font=("Segoe UI", 9, "bold"),
        )
        self.status_text_label.pack(side="left", fill="x", expand=True, padx=(8, 0))
        status_panel.configure(bg="#f3f4f6")

        self.root.bind("<Delete>", lambda _e: self.remove_selected())
        tree.bind("<Double-1>", self._on_row_double_click)
        tree.bind("<Button-3>", self._on_row_right_click)

        row_context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#111827",
            fg="#e2e8f0",
            activebackground="#1f2937",
            activeforeground="#ffffff",
            bd=1,
            relief="solid",
            font=("Segoe UI", 9),
        )
        self.row_context_menu = row_context_menu

    def _on_row_double_click(self, _event: Any) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            return

        row = self.rows.get(selected[0])
        if not row:
            return

        report_value = str(row.get("report") or "").strip()
        if report_value:
            report_path = Path(report_value)
            if report_path.exists():
                self._show_report_window(
                    report_path,
                    row=row,
                    previous_stats=self.previous_report_stats.get(selected[0]),
                )
                return

        output_value = str(row.get("output") or "").strip()
        if output_value:
            output_path = Path(output_value)
            if output_path.exists() or output_path.parent.exists():
                try:
                    if sys.platform == "win32":
                        os.startfile(
                            str(
                                output_path.parent
                                if output_path.is_dir()
                                else output_path.parent
                            )
                        )
                    elif sys.platform == "darwin":
                        subprocess.run(["open", str(output_path.parent)], check=False)
                    else:
                        subprocess.run(
                            ["xdg-open", str(output_path.parent)], check=False
                        )
                except Exception as exc:
                    logger.exception("Unable to open output path %s", output_path)
                    messagebox.showerror(
                        get_localized_text("open_output_folder"),
                        f"Unable to open folder: {exc}",
                    )
                return

        messagebox.showinfo(
            get_localized_text("view_report"),
            get_localized_text("row_no_report"),
        )

    def _on_row_right_click(self, event: Any) -> None:
        if self.tree is None or self.row_context_menu is None:
            return

        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        row = self.rows.get(row_id)
        self.row_context_menu.delete(0, "end")
        if self._row_has_openable_report(row):
            self.row_context_menu.add_command(
                label=get_localized_text("open_report"),
                command=self._open_report_from_context_menu,
            )
        else:
            if row and str(row.get("status", "")).upper() == "READY":
                self.row_context_menu.add_command(
                    label=get_localized_text("convert"),
                    command=self._convert_selected_from_context_menu,
                )
            self.row_context_menu.add_command(
                label=get_localized_text("remove"),
                command=self._remove_selected_from_context_menu,
            )
        try:
            self.row_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.row_context_menu.grab_release()

    def _row_has_openable_report(self, row: RowData | None) -> bool:
        if not row or str(row.get("status", "")).upper() != "OK":
            return False

        report_value = str(row.get("report") or "").strip()
        if not report_value:
            return False
        return Path(report_value).exists()

    def _open_report_from_context_menu(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            return
        row = self.rows.get(selected[0])
        if not self._row_has_openable_report(row):
            return
        self._show_selected_ok_report()

    def _convert_selected_from_context_menu(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            return
        row = self.rows.get(selected[0])
        if not row or str(row.get("status", "")).upper() != "READY":
            return
        self._convert_items(
            [selected[0]],
            summary_title=get_localized_text("selected_conversion_finished"),
        )

    def _remove_selected_from_context_menu(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            return

        row = self.rows.get(selected[0], {})
        file_name = Path(str(row.get("file") or "selected file")).name
        self.remove_selected()
        self._update_status(get_localized_text("status_row_removed", name=file_name))

    def _update_table_scrollbar(self) -> None:
        if self.tree is None or self.yscroll is None or self.xscroll is None:
            return
        tree = self.tree
        row_count = len(tree.get_children())
        if row_count <= 10:
            self.yscroll.grid_remove()
            self.xscroll.grid_remove()
        else:
            self.yscroll.grid()
            self.xscroll.grid()

    def _refresh_summary_cards(self) -> None:
        files_total = len(self.rows)
        ready_total = sum(
            1
            for row in self.rows.values()
            if str(row.get("status", "")).upper() == "READY"
        )
        ok_total = sum(
            1
            for row in self.rows.values()
            if str(row.get("status", "")).upper() == "OK"
        )
        failed_total = sum(
            1
            for row in self.rows.values()
            if str(row.get("status", "")).upper() == "FAILED"
        )
        skipped_total = sum(
            1
            for row in self.rows.values()
            if str(row.get("status", "")).upper() == "SKIPPED"
        )

        mapping = {
            "files": files_total,
            "ready": ready_total,
            "ok": ok_total,
            "failed": failed_total,
            "skipped": skipped_total,
        }
        for key, value in mapping.items():
            label = self.summary_cards.get(key)
            if label is not None:
                label.configure(text=str(value))
        self._update_table_scrollbar()

    def _handle_summary_card_click(self, key: str) -> None:
        status_key = key.upper()
        if status_key == "OK":
            if not any(
                str(row.get("status", "")).upper() == "OK" for row in self.rows.values()
            ):
                messagebox.showinfo(
                    get_localized_text("summary_ok_report"),
                    get_localized_text("status_no_files_loaded"),
                )
                return
            self._show_selected_ok_report()
            return

        if status_key == "FAILED":
            failed_rows = [
                row
                for row in self.rows.values()
                if str(row.get("status", "")).upper() == "FAILED"
            ]
            if not failed_rows:
                messagebox.showinfo(
                    get_localized_text(
                        "status_done_summary", ok=0, failed=0, skipped=0
                    ),
                    get_localized_text("no_failed_rows"),
                )
                return

            details = []
            for row in failed_rows:
                file_name = Path(str(row.get("file") or "unknown")).name
                error_text = str(row.get("error") or "Unknown error")
                details.append(f"- {file_name}: {error_text}")

            messagebox.showerror(
                "Failed conversion details",
                "\n".join(details),
            )

    def _show_selected_ok_report(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            messagebox.showinfo(
                get_localized_text("summary_ok_report"),
                get_localized_text("please_select_one_row"),
            )
            return

        row = self.rows.get(selected[0])
        if not row:
            return

        if str(row.get("status", "")).upper() != "OK":
            messagebox.showinfo(
                get_localized_text("summary_ok_report"),
                get_localized_text("please_select_successful_row"),
            )
            return

        report_value = str(row.get("report") or "").strip()
        if not report_value:
            messagebox.showinfo(
                get_localized_text("view_report"),
                get_localized_text("row_no_report"),
            )
            return

        report_path = Path(report_value)
        if not report_path.exists():
            messagebox.showwarning(
                get_localized_text("view_report"),
                get_localized_text("report_missing", report_path=report_path),
            )
            return

        self._show_report_window(
            report_path,
            row=row,
            previous_stats=self.previous_report_stats.get(selected[0]),
        )

    def _setup_drag_and_drop(self) -> None:
        # Optional support: enabled only when TkDND package is present in the runtime.
        try:
            self.root.tk.call("package", "require", "tkdnd")
            dnd_tree = cast(Any, self.tree)
            dnd_tree.drop_target_register("DND_Files")
            dnd_tree.dnd_bind("<<Drop>>", self._on_drop_files)
            self._drag_drop_enabled = True
            logger.info("GUI drag-and-drop enabled")
        except Exception:
            self._drag_drop_enabled = False
            logger.info("GUI drag-and-drop not available (TkDND not installed)")

    def _on_drop_files(self, event: Any) -> None:
        try:
            dropped = [Path(item) for item in self.root.tk.splitlist(event.data)]
        except Exception:
            dropped = []
        added = self._add_paths(dropped)
        self._update_status(
            f"Loaded {len(self.rows)} file(s), added {added} from drag-and-drop"
        )

    def _add_paths(self, paths: list[Path]) -> int:
        tree = self._get_tree()
        added_count = 0
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in {
                ".csv",
                ".xlsx",
                ".pdf",
            }:
                continue

            key = str(path)
            if key in self.rows:
                continue

            detection = self.service.detect(path)
            row: RowData = {
                "file": str(path),
                "detected": detection.converter or "",
                "module": detection.module_name or "",
                "status": "READY" if detection.converter else "SKIPPED",
                "output": "",
                "report": "",
                "error": (
                    ""
                    if detection.converter
                    else get_localized_text("no_converter_detected_row")
                ),
            }
            self.rows[key] = row
            tree.insert(
                "",
                "end",
                iid=key,
                values=tuple(
                    row[col]
                    for col in (
                        "file",
                        "detected",
                        "module",
                        "status",
                        "output",
                        "report",
                        "error",
                    )
                ),
            )
            added_count += 1

        self._refresh_summary_cards()
        return added_count

    def _set_output_language(self) -> None:
        selected = self.output_language_var.get()
        app_config.OUTPUT_LANGUAGE = (
            "french" if selected == get_localized_text("french_label") else "english"
        )
        self._update_status(
            get_localized_text("output_language_status", selected=selected)
        )

    def _set_progress(self, current: int, total: int) -> None:
        total_safe = max(total, 1)
        self.progress.configure(maximum=total_safe, value=min(current, total_safe))
        self.progress_label_var.set(f"{current}/{total}")
        self.root.update_idletasks()

    def add_files(self) -> None:
        file_paths = filedialog.askopenfilenames(
            title=get_localized_text("select_bank_files"),
            filetypes=[
                (get_localized_text("supported_files"), "*.csv *.xlsx *.pdf"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx"),
                ("PDF", "*.pdf"),
                (get_localized_text("all_files"), "*.*"),
            ],
        )
        if not file_paths:
            return

        added_count = self._add_paths([Path(p) for p in file_paths])

        logger.info(
            "GUI loaded %d file(s), %d newly added", len(self.rows), added_count
        )
        self._update_status(
            get_localized_text(
                "status_loaded_summary", count=len(self.rows), added=added_count
            )
        )

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(
            title=get_localized_text("select_folder_bank_files")
        )
        if not folder:
            return

        base = Path(folder)
        files = [p for p in sorted(base.iterdir()) if p.is_file()]
        added_count = self._add_paths(files)
        logger.info("GUI imported folder %s, %d file(s) added", base, added_count)
        self._update_status(
            get_localized_text(
                "status_loaded_folder_summary",
                count=len(self.rows),
                added=added_count,
            )
        )

    def remove_selected(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            return
        for iid in selected:
            tree.delete(iid)
            self.rows.pop(iid, None)
            self.previous_report_stats.pop(iid, None)
        logger.info("GUI removed %d selected file(s)", len(selected))
        self._refresh_summary_cards()
        self._update_status(
            get_localized_text("status_loaded_count", count=len(self.rows))
        )

    def clear_rows(self) -> None:
        tree = self._get_tree()
        for iid in tree.get_children():
            tree.delete(iid)
        self.rows.clear()
        self.previous_report_stats.clear()
        self._refresh_summary_cards()
        logger.info("GUI cleared file list")
        self._update_status(get_localized_text("status_no_files_loaded"))

    def exit_app(self) -> None:
        logger.info("GUI exit requested")
        self.root.destroy()

    def convert_selected(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            messagebox.showinfo(
                get_localized_text("convert_selected"),
                get_localized_text("please_select_rows"),
            )
            return
        self._convert_items(
            selected, summary_title=get_localized_text("selected_conversion_finished")
        )

    def convert_all(self) -> None:
        tree = self._get_tree()
        all_items = list(tree.get_children())
        if not all_items:
            messagebox.showinfo(
                get_localized_text("convert_all"),
                get_localized_text("no_files_to_convert"),
            )
            return
        self._convert_items(
            all_items, summary_title=get_localized_text("full_conversion_finished")
        )

    def retry_failed(self) -> None:
        failed_items = [
            iid
            for iid, row in self.rows.items()
            if str(row.get("status", "")) in {"FAILED", "SKIPPED"}
        ]
        if not failed_items:
            messagebox.showinfo(
                get_localized_text("retry_failed"), get_localized_text("no_failed_rows")
            )
            return
        self._convert_items(
            failed_items, summary_title=get_localized_text("retry_finished")
        )

    def _resolve_default_output_folder(self) -> Path | None:
        candidate = Path(
            str(getattr(app_config, "DOSSIER_SOURCE", "") or "")
        ).expanduser()
        if str(candidate).strip() and candidate.exists():
            return candidate
        return None

    def _find_import_output_folders(self, base_folder: Path) -> list[Path]:
        return sorted(
            [
                item
                for item in base_folder.iterdir()
                if item.is_dir() and item.name.startswith("Import_")
            ],
            key=lambda path: path.name.casefold(),
        )

    def _open_default_output_folder_choice(self) -> bool:
        default_folder = self._resolve_default_output_folder()
        if default_folder is None:
            messagebox.showwarning(
                get_localized_text("open_output_folder"),
                get_localized_text(
                    "folder_missing",
                    folder=getattr(app_config, "DOSSIER_SOURCE", ""),
                ),
            )
            return False

        import_folders = self._find_import_output_folders(default_folder)
        if not import_folders:
            messagebox.showinfo(
                get_localized_text("open_output_folder"),
                get_localized_text(
                    "no_import_output_folders",
                    folder=default_folder,
                ),
            )
            return False

        selected_folder = filedialog.askdirectory(
            title=get_localized_text("select_output_folder"),
            initialdir=str(default_folder),
            mustexist=True,
        )
        if not selected_folder:
            return False

        self._open_folder_path(Path(selected_folder))
        return True

    def _open_folder_path(self, folder: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
            logger.info("Opened output folder: %s", folder)
        except Exception as exc:
            logger.exception("Unable to open output folder %s", folder)
            messagebox.showerror(
                get_localized_text("open_output_folder"),
                f"Unable to open folder: {exc}",
            )

    def open_output_folder(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            self._open_default_output_folder_choice()
            return

        row = self.rows.get(selected[0])
        if not row:
            return

        output_value = str(row.get("output") or "").strip()
        if not output_value:
            if not self._open_default_output_folder_choice():
                messagebox.showinfo(
                    get_localized_text("open_output_folder"),
                    get_localized_text("row_no_output_path"),
                )
            return

        out_path = Path(output_value)
        folder = out_path if out_path.is_dir() else out_path.parent
        if not folder.exists():
            if not self._open_default_output_folder_choice():
                messagebox.showwarning(
                    get_localized_text("open_output_folder"),
                    get_localized_text("folder_missing", folder=folder),
                )
            return

        self._open_folder_path(folder)

    def _open_report_file(self, report_path: Path) -> None:
        """Open the raw report file in the default system application."""
        try:
            if sys.platform == "win32":
                os.startfile(str(report_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(report_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(report_path)], check=False)
            logger.info("Opened report: %s", report_path)
        except Exception as exc:
            logger.exception("Unable to open report %s", report_path)
            messagebox.showerror(
                get_localized_text("view_report"),
                get_localized_text("open_report_error", exc=exc),
            )

    def _resolve_report_display_name(
        self,
        report_path: Path,
        stats: Any = None,
        row: dict[str, str | Path | None] | None = None,
    ) -> str:
        converter_name = ""
        if stats is not None:
            converter_name = str(getattr(stats, "converter_name", "") or "")
        if not converter_name and row is not None:
            converter_name = str(row.get("detected") or row.get("module") or "")

        normalized = converter_name.strip().casefold()
        if "mastercard" in normalized:
            return get_localized_text("report_label_mastercard")
        if (
            normalized in {"amex", "amex_csv", "amex_xlsx"}
            or "american express" in normalized
        ):
            return get_localized_text("report_label_amex")
        if "argenta" in normalized:
            return get_localized_text("report_label_argenta")
        if "keytrade" in normalized:
            return get_localized_text("report_label_keytrade")

        source_name = ""
        if stats is not None:
            source_name = str(getattr(stats, "input_file_name", "") or "")
        if not source_name and row is not None:
            source_name = Path(str(row.get("file") or report_path.stem)).stem
        if not source_name:
            source_name = report_path.stem.replace("_report", "")
        return get_localized_text("report_label_generic", name=Path(source_name).stem)

    def _show_report_window(
        self,
        report_path: Path,
        row: dict[str, str | Path | None] | None = None,
        previous_stats: Any = None,
    ) -> None:
        """Display a dedicated statistics window with summary metrics and details."""
        from scripts.converters.statistics import ConversionStatistics

        try:
            stats = ConversionStatistics.from_file(report_path)
        except Exception as exc:  # pragma: no cover - fallback only
            logger.warning("Could not parse JSON report %s: %s", report_path, exc)
            stats = None

        report_display_name = self._resolve_report_display_name(
            report_path, stats=stats, row=row
        )
        window = tk.Toplevel(self.root)
        window.title(
            get_localized_text("report_window_title", name=report_display_name)
        )
        window.geometry("960x700")
        window.minsize(820, 560)
        window.configure(bg="#edf3ff")

        main = tk.Frame(window, bg="#edf3ff", padx=14, pady=14)
        main.pack(fill="both", expand=True)

        header = tk.Frame(
            main,
            bg="#0f172a",
            padx=18,
            pady=14,
            highlightbackground="#dfe9ff",
            highlightthickness=1,
        )
        header.pack(fill="x")
        tk.Label(
            header,
            text=get_localized_text("financial_dashboard"),
            font=("Segoe UI", 14, "bold"),
            fg="#f8fbff",
            bg="#0f172a",
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            header,
            text=report_display_name,
            font=("Segoe UI", 10),
            fg="#dfeaff",
            bg="#0f172a",
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        summary = (
            stats.summary()
            if stats
            else {
                "currency": "EUR",
                "total_transactions": 0,
                "total_revenues": 0.0,
                "total_expenses": 0.0,
                "net_movement": 0.0,
                "skipped_count": 0,
            }
        )

        def as_float(value: object, default: float = 0.0) -> float:
            try:
                return float(str(value))
            except (TypeError, ValueError):
                return default

        def as_int(value: object, default: int = 0) -> int:
            try:
                return int(str(value))
            except (TypeError, ValueError):
                return default

        cards = tk.Frame(main, bg="#edf3ff")
        cards.pack(fill="x", pady=(14, 12))
        metrics = [
            (
                "total_revenues",
                get_localized_text("revenues"),
                as_float(summary.get("total_revenues", 0.0)),
                "#dff5e7",
                "#1d7a4f",
            ),
            (
                "total_expenses",
                get_localized_text("expenses"),
                as_float(summary.get("total_expenses", 0.0)),
                "#ffe5e5",
                "#c73a3a",
            ),
            (
                "net_movement",
                get_localized_text("net"),
                as_float(summary.get("net_movement", 0.0)),
                "#e7efff",
                "#3257d6",
            ),
            (
                "total_transactions",
                get_localized_text("transaction_short"),
                as_int(summary.get("total_transactions", 0)),
                "#f7eaff",
                "#7a4bb7",
            ),
            (
                "skipped_count",
                get_localized_text("skipped"),
                as_int(summary.get("skipped_count", 0)),
                "#fff4d9",
                "#b36a00",
            ),
        ]

        previous_summary = (
            previous_stats.summary() if previous_stats is not None else None
        )
        for index, (metric_key, label, value, color, accent) in enumerate(metrics):
            card = tk.Frame(
                cards,
                bg=color,
                highlightbackground=accent,
                highlightthickness=1,
                padx=12,
                pady=12,
            )
            card.grid(row=0, column=index, padx=(0, 8), sticky="nsew")

            accent_bar = tk.Frame(card, bg=accent, height=4)
            accent_bar.pack(fill="x", pady=(0, 8), padx=0)

            tk.Label(
                card, text=label, font=("Segoe UI", 9, "bold"), fg=accent, bg=color
            ).pack(anchor="w")
            tk.Label(
                card,
                text=f"{value:,.2f}" if isinstance(value, float) else str(value),
                font=("Segoe UI", 13, "bold"),
                fg="#0b172a",
                bg=color,
            ).pack(anchor="w", pady=(4, 0))
            tk.Label(card, text=str(summary["currency"]), fg="#53657a", bg=color).pack(
                anchor="w"
            )

            previous_metric_value = None
            if previous_summary is not None and metric_key in previous_summary:
                previous_metric_value = float(previous_summary[metric_key])

            current_metric_value = float(value)
            if previous_metric_value is None:
                signal = get_localized_text("stat_unchanged")
            elif current_metric_value > previous_metric_value:
                signal = get_localized_text("stat_up")
            elif current_metric_value < previous_metric_value:
                signal = get_localized_text("stat_down")
            else:
                signal = get_localized_text("stat_unchanged")
            tk.Label(
                card, text=signal, fg=accent, bg=color, font=("Segoe UI", 8, "bold")
            ).pack(anchor="w", pady=(6, 0))

        for col_index in range(len(metrics)):
            cards.columnconfigure(col_index, weight=1)

        if stats and stats.payment_type_breakdown:
            payment_breakdown_frame = tk.LabelFrame(
                main,
                text=get_localized_text("payment_mix"),
                bg="#ffffff",
                fg="#0f172a",
                padx=10,
                pady=8,
            )
            payment_breakdown_frame.pack(fill="both", expand=True, pady=(0, 12))
            payment_table = ttk.Treeview(
                payment_breakdown_frame,
                columns=("payment", "count", "amount"),
                show="headings",
                height=8,
            )
            payment_table.heading("payment", text=get_localized_text("payment"))
            payment_table.heading("count", text=get_localized_text("transactions"))
            payment_table.heading("amount", text=get_localized_text("amount"))
            payment_table.column("payment", width=260, anchor="w")
            payment_table.column("count", width=100, anchor="center")
            payment_table.column("amount", width=140, anchor="e")
            payment_table.pack(fill="both", expand=True)
            for item in stats.payment_type_breakdown:
                payment_table.insert(
                    "",
                    "end",
                    values=(
                        f"{item.payment_code} - {item.payment_info}",
                        item.transaction_count,
                        f"{item.total_amount:,.2f} {stats.currency}",
                    ),
                )

        details_panel = tk.LabelFrame(
            main,
            text=get_localized_text("detailed_report"),
            bg="#ffffff",
            fg="#0f172a",
            padx=10,
            pady=8,
        )
        details_panel.pack(fill="both", expand=True)
        text_widget = scrolledtext.ScrolledText(
            details_panel,
            wrap=tk.WORD,
            height=12,
            font=("Consolas", 10),
            padx=8,
            pady=8,
            bg="#f8fafc",
        )
        text_widget.pack(fill="both", expand=True)
        text_widget.insert(
            tk.END,
            (
                stats.to_text()
                if stats
                else report_path.read_text(encoding="utf-8", errors="replace")
            ),
        )
        text_widget.configure(state="disabled")

        buttons = tk.Frame(main, bg="#edf3ff")
        buttons.pack(fill="x", pady=(12, 0))
        tk.Button(
            buttons,
            text=get_localized_text("open_raw_report"),
            bg="#e7f2ff",
            fg="#123d7a",
            activebackground="#d9ebff",
            command=lambda: self._open_report_file(report_path),
            relief="flat",
            padx=12,
            pady=6,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons,
            text=get_localized_text("close"),
            bg="#f8dfe3",
            fg="#7f2431",
            activebackground="#f9c8d0",
            command=window.destroy,
            relief="flat",
            padx=12,
            pady=6,
        ).pack(side="left")

        if stats and stats.payment_type_breakdown:
            ttk_payment_breakdown_frame = ttk.LabelFrame(
                main, text=get_localized_text("payment_breakdown"), padding=8
            )
            ttk_payment_breakdown_frame.pack(fill="both", expand=True, pady=(0, 12))
            payment_table = ttk.Treeview(
                ttk_payment_breakdown_frame,
                columns=("payment", "count", "amount"),
                show="headings",
                height=8,
            )
            payment_table.heading("payment", text=get_localized_text("payment"))
            payment_table.heading("count", text=get_localized_text("transactions"))
            payment_table.heading("amount", text=get_localized_text("amount"))
            payment_table.column("payment", width=260, anchor="w")
            payment_table.column("count", width=100, anchor="center")
            payment_table.column("amount", width=140, anchor="e")
            payment_table.pack(fill="both", expand=True)
            for item in stats.payment_type_breakdown:
                payment_table.insert(
                    "",
                    "end",
                    values=(
                        f"{item.payment_code} - {item.payment_info}",
                        item.transaction_count,
                        f"{item.total_amount:,.2f} {stats.currency}",
                    ),
                )

        ttk_details_panel = ttk.LabelFrame(
            main, text=get_localized_text("detailed_report"), padding=8
        )
        ttk_details_panel.pack(fill="both", expand=True)
        text_widget = scrolledtext.ScrolledText(
            ttk_details_panel,
            wrap=tk.WORD,
            height=12,
            font=("Consolas", 10),
            padx=8,
            pady=8,
        )
        text_widget.pack(fill="both", expand=True)
        text_widget.insert(
            tk.END,
            (
                stats.to_text()
                if stats
                else report_path.read_text(encoding="utf-8", errors="replace")
            ),
        )
        text_widget.configure(state="disabled")

        action_buttons = ttk.Frame(main)
        action_buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(
            action_buttons,
            text=get_localized_text("open_raw_report"),
            command=lambda: self._open_report_file(report_path),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            action_buttons, text=get_localized_text("close"), command=window.destroy
        ).pack(side="left")

    def view_report(self) -> None:
        tree = self._get_tree()
        selected = list(tree.selection())
        if not selected:
            messagebox.showinfo(
                get_localized_text("view_report"),
                get_localized_text("please_select_one_row"),
            )
            return

        row = self.rows.get(selected[0])
        if not row:
            return

        report_value = str(row.get("report") or "").strip()
        if not report_value:
            messagebox.showinfo(
                get_localized_text("view_report"), get_localized_text("row_no_report")
            )
            return

        report_path = Path(report_value)
        if not report_path.exists():
            messagebox.showwarning(
                get_localized_text("view_report"),
                get_localized_text("report_missing", report_path=report_path),
            )
            return

        self._show_report_window(
            report_path,
            row=row,
            previous_stats=self.previous_report_stats.get(selected[0]),
        )

    def _convert_items(self, item_ids: list[str], summary_title: str) -> None:
        ok_count = 0
        fail_count = 0
        skip_count = 0
        total = len(item_ids)
        self._set_progress(0, total)

        for index, iid in enumerate(item_ids, start=1):
            row = self.rows.get(iid)
            if not row:
                self._set_progress(index, total)
                continue

            file_path = Path(str(row["file"]))
            detected = self._parse_converter_name(row.get("detected"))
            module = self._parse_module_name(row.get("module"))

            if detected is None or module is None:
                detection = self.service.detect(file_path)
                detected = detection.converter
                module = detection.module_name
                row["detected"] = detected or ""
                row["module"] = module or ""

            if detected is None or module is None:
                row["status"] = "SKIPPED"
                row["output"] = ""
                row["error"] = get_localized_text("no_converter_detected_row")
                skip_count += 1
                self._refresh_row(iid)
                self._set_progress(index, total)
                continue

            result = self.service.convert(file_path, detected, module)
            row["status"] = result.status
            row["output"] = str(result.output_path) if result.output_path else ""
            row["report"] = str(result.report_path) if result.report_path else ""
            row["error"] = result.error or ""
            self.previous_report_stats[iid] = result.previous_statistics

            if result.status == "OK":
                ok_count += 1
            else:
                fail_count += 1

            self._refresh_row(iid)
            self._set_progress(index, total)

        self._refresh_summary_cards()
        tone = (
            "success"
            if fail_count == 0 and ok_count > 0
            else "warning" if fail_count > 0 else "info"
        )
        self._update_status(
            get_localized_text(
                "status_done_summary",
                ok=ok_count,
                failed=fail_count,
                skipped=skip_count,
            ),
            tone=tone,
        )
        logger.info(
            "GUI conversion completed: OK=%d Failed=%d Skipped=%d",
            ok_count,
            fail_count,
            skip_count,
        )

    def _refresh_row(self, iid: str) -> None:
        row = self.rows[iid]
        tree = self._get_tree()
        tree.item(
            iid,
            values=tuple(
                row[col]
                for col in (
                    "file",
                    "detected",
                    "module",
                    "status",
                    "output",
                    "report",
                    "error",
                )
            ),
        )

    def _update_status(self, text: str, tone: str = "info") -> None:
        self.status_var.set(text)
        palette = {
            "info": ("#1d4ed8", "#f3f4f6"),
            "success": ("#166534", "#f0fdf4"),
            "warning": ("#92400e", "#fff7ed"),
            "error": ("#991b1b", "#fef2f2"),
        }
        fg_color, bg_color = palette.get(tone, palette["info"])
        if self.status_icon is not None:
            self.status_icon.configure(fg=fg_color, bg=bg_color)
        if self.status_panel is not None:
            self.status_panel.configure(bg=bg_color)
        if self.status_text_label is not None:
            self.status_text_label.configure(bg=bg_color, fg="#1f2937")


def main() -> None:
    configure_logging()
    startup_warnings = [
        m for m in app_config.validate_startup_settings() if m.startswith("Warning:")
    ]
    for message in startup_warnings:
        logger.warning(message)

    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    ConversionGuiApp(root)
    root.minsize(900, 460)
    if startup_warnings:
        messagebox.showwarning(
            get_localized_text("configuration_warnings"),
            get_localized_text(
                "config_recovered",
                messages="\n".join(startup_warnings),
            ),
        )
    root.mainloop()


if __name__ == "__main__":
    main()
