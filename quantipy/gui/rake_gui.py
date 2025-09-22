"""Tkinter GUI for configuring and executing Quantipy rake weighting."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from quantipy.core.weights.rim import Rake
from quantipy.gui.target_utils import format_target_values, parse_target_inputs


@dataclass
class TargetSpec:
    """Container storing a single set of raking targets."""

    column: str
    values: Dict[str, float]
    original_total: float
    uid: Optional[str] = None

    def as_rake_target(self) -> Dict[str, Dict[str, float]]:
        return {self.column: self.values}


class RakeGUI(tk.Tk):
    """Tkinter based interface for Quantipy's raking engine."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Quantipy Rake Weighting")
        self.geometry("1000x720")

        self.df: Optional[pd.DataFrame] = None
        self.dataset_path: Optional[Path] = None
        self.targets: list[Dict[str, Dict[str, float]]] = []
        self.target_specs: list[TargetSpec] = []
        self.code_entries: dict[str, ttk.Entry] = {}
        self.current_column: Optional[str] = None
        self._id_counter = count(1)

        self.weight_column_var = tk.StringVar(value="weight")
        self.status_var = tk.StringVar(value="Load a dataset to begin.")

        self._build_widgets()
        self._update_run_state()

    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        top.columnconfigure(1, weight=1)

        load_btn = ttk.Button(top, text="Load CSV…", command=self.load_data)
        load_btn.grid(row=0, column=0, padx=(0, 8))

        self.dataset_label = ttk.Label(top, text="No dataset loaded")
        self.dataset_label.grid(row=0, column=1, sticky="w")

        weight_frame = ttk.Frame(top)
        weight_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(weight_frame, text="Weight column:").pack(side="left")
        self.weight_combo = ttk.Combobox(
            weight_frame,
            textvariable=self.weight_column_var,
            width=20,
            state="normal",
        )
        self.weight_combo.pack(side="left", padx=(4, 4))
        ttk.Label(weight_frame, text="(existing or new column name)").pack(side="left")

        content = ttk.Frame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        columns_frame = ttk.LabelFrame(content, text="Columns")
        columns_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.rowconfigure(0, weight=1)

        self.column_list = tk.Listbox(columns_frame, exportselection=False)
        self.column_list.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            columns_frame, orient="vertical", command=self.column_list.yview
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.column_list.configure(yscrollcommand=scroll.set)
        self.column_list.bind("<<ListboxSelect>>", self.display_codes)

        editor_frame = ttk.LabelFrame(content, text="Target editor")
        editor_frame.grid(row=0, column=1, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)

        self.target_editor = ttk.Frame(editor_frame)
        self.target_editor.grid(row=0, column=0, sticky="nsew")
        editor_frame.rowconfigure(0, weight=1)

        editor_buttons = ttk.Frame(editor_frame)
        editor_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.add_target_btn = ttk.Button(
            editor_buttons,
            text="Save targets",
            command=self.add_current_target,
            state="disabled",
        )
        self.add_target_btn.pack(side="left")
        self.reset_entries_btn = ttk.Button(
            editor_buttons,
            text="Clear inputs",
            command=self._clear_entries,
            state="disabled",
        )
        self.reset_entries_btn.pack(side="left", padx=(6, 0))

        targets_frame = ttk.LabelFrame(content, text="Current targets")
        targets_frame.grid(row=1, column=1, sticky="nsew")
        targets_frame.columnconfigure(0, weight=1)
        targets_frame.rowconfigure(0, weight=1)

        columns = ("column", "values", "total")
        self.target_tree = ttk.Treeview(
            targets_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse",
        )
        for col, heading in zip(columns, ["Column", "Targets (%)", "Original total"]):
            self.target_tree.heading(col, text=heading)
            anchor = "center" if col != "values" else "w"
            self.target_tree.column(col, anchor=anchor, stretch=True)
        self.target_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(
            targets_frame, orient="vertical", command=self.target_tree.yview
        )
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.target_tree.configure(yscrollcommand=tree_scroll.set)

        targets_buttons = ttk.Frame(targets_frame)
        targets_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            targets_buttons, text="Edit", command=self.edit_selected_target
        ).pack(side="left")
        ttk.Button(
            targets_buttons, text="Remove", command=self.remove_selected_target
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            targets_buttons, text="Clear all", command=self.clear_all_targets
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            targets_buttons, text="Save scheme…", command=self.save_targets
        ).pack(side="right")
        ttk.Button(
            targets_buttons, text="Load scheme…", command=self.load_targets
        ).pack(side="right", padx=(0, 6))

        report_frame = ttk.Frame(self)
        report_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        report_frame.columnconfigure(0, weight=1)
        report_frame.columnconfigure(1, weight=1)
        report_frame.rowconfigure(1, weight=1)

        self.run_button = ttk.Button(
            report_frame,
            text="Run weighting",
            command=self.run_weighting,
            state="disabled",
        )
        self.run_button.grid(row=0, column=0, sticky="w", pady=(0, 6))

        summary_frame = ttk.LabelFrame(report_frame, text="Weighting summary")
        summary_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.rowconfigure(0, weight=1)
        self.summary_tree = ttk.Treeview(
            summary_frame,
            columns=("metric", "value"),
            show="headings",
            height=8,
        )
        self.summary_tree.heading("metric", text="Metric")
        self.summary_tree.heading("value", text="Value")
        self.summary_tree.column("metric", width=220, anchor="w")
        self.summary_tree.column("value", anchor="center")
        self.summary_tree.grid(row=0, column=0, sticky="nsew")
        summary_scroll = ttk.Scrollbar(
            summary_frame, orient="vertical", command=self.summary_tree.yview
        )
        summary_scroll.grid(row=0, column=1, sticky="ns")
        self.summary_tree.configure(yscrollcommand=summary_scroll.set)

        log_frame = ttk.LabelFrame(report_frame, text="Activity log")
        log_frame.grid(row=1, column=1, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.output = tk.Text(log_frame, height=10, state="disabled")
        self.output.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.output.yview
        )
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=log_scroll.set)

        status_bar = ttk.Label(
            self, textvariable=self.status_var, relief="sunken", anchor="w"
        )
        status_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 10))

    # ------------------------------------------------------------------
    def load_data(self) -> None:
        """Load a CSV file and populate the column list."""
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self.df = pd.read_csv(path)
        except Exception as err:  # pragma: no cover - GUI feedback
            messagebox.showerror("Load error", str(err))
            return

        self.dataset_path = Path(path)
        self.dataset_label.configure(text=self.dataset_path.name)

        self.column_list.delete(0, tk.END)
        for col in self.df.columns:
            self.column_list.insert(tk.END, col)

        self.weight_combo["values"] = tuple(self.df.columns)
        if "weight" in self.df.columns:
            self.weight_column_var.set("weight")
        else:
            self.weight_column_var.set(self.weight_column_var.get() or "weight")

        self._reset_targets()
        self._set_status(f"Loaded data with {len(self.df)} rows.")
        self._append_log(f"Dataset loaded from {self.dataset_path}.")
        self._update_run_state()

    # ------------------------------------------------------------------
    def display_codes(
        self, event: Optional[tk.Event] = None
    ) -> None:  # pragma: no cover - GUI callback
        selection = self.column_list.curselection()
        if not selection:
            self._clear_target_editor()
            return
        column = self.column_list.get(selection[0])
        self._render_target_editor(column)

    # ------------------------------------------------------------------
    def _render_target_editor(
        self, column: str, preset: Optional[Dict[str, float]] = None
    ) -> None:
        if self.df is None:
            return
        for widget in self.target_editor.winfo_children():
            widget.destroy()
        self.code_entries.clear()

        ttk.Label(self.target_editor, text=f"Targets for {column} (%)").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        codes = self.df[column].dropna().unique().tolist()
        codes.sort(key=lambda value: str(value))
        if not codes:
            ttk.Label(self.target_editor, text="No codes found for this column.").grid(
                row=1, column=0, sticky="w"
            )
        for r, code in enumerate(codes, start=1):
            ttk.Label(self.target_editor, text=str(code)).grid(
                row=r, column=0, sticky="w"
            )
            entry = ttk.Entry(self.target_editor, width=10)
            entry.grid(row=r, column=1, sticky="w")
            if preset and str(code) in preset:
                entry.insert(0, f"{preset[str(code)]:.2f}")
            self.code_entries[str(code)] = entry

        self.current_column = column
        self.add_target_btn.configure(state="normal")
        self.reset_entries_btn.configure(state="normal")

    # ------------------------------------------------------------------
    def _clear_target_editor(self) -> None:
        for widget in self.target_editor.winfo_children():
            widget.destroy()
        self.code_entries.clear()
        self.current_column = None
        self.add_target_btn.configure(state="disabled")
        self.reset_entries_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    def _clear_entries(self) -> None:  # pragma: no cover - GUI callback
        for entry in self.code_entries.values():
            entry.delete(0, tk.END)

    # ------------------------------------------------------------------
    def add_current_target(self) -> None:  # pragma: no cover - GUI callback
        if self.current_column is None:
            return
        raw_inputs = {code: entry.get() for code, entry in self.code_entries.items()}
        try:
            normalised, total = parse_target_inputs(raw_inputs)
        except ValueError as err:
            messagebox.showerror("Target error", str(err))
            return

        self._remove_existing_spec_for_column(self.current_column)
        spec = TargetSpec(
            column=self.current_column, values=normalised, original_total=total
        )
        self._store_spec(spec)
        self._clear_entries()
        self._append_log(
            f"Targets set for {spec.column}: {format_target_values(spec.values)}"
        )
        if not math.isclose(total, 100.0, rel_tol=1e-4, abs_tol=1e-4):
            self._set_status(
                f"{spec.column} targets normalised to 100% (original total {total:.2f})."
            )
        else:
            self._set_status(f"Targets saved for {spec.column}.")

    # ------------------------------------------------------------------
    def _remove_existing_spec_for_column(self, column: str) -> None:
        removed = [spec for spec in self.target_specs if spec.column == column]
        if not removed:
            return
        self.target_specs = [
            spec for spec in self.target_specs if spec.column != column
        ]
        for item in removed:
            if item.uid:
                self.target_tree.delete(item.uid)
        self._sync_rake_targets()
        self._update_run_state()

    # ------------------------------------------------------------------
    def _store_spec(self, spec: TargetSpec) -> None:
        spec.uid = str(next(self._id_counter))
        self.target_specs.append(spec)
        self.target_tree.insert(
            "",
            tk.END,
            iid=spec.uid,
            values=(
                spec.column,
                format_target_values(spec.values),
                f"{spec.original_total:.2f}",
            ),
        )
        self._sync_rake_targets()
        self._update_run_state()

    # ------------------------------------------------------------------
    def edit_selected_target(self) -> None:  # pragma: no cover - GUI callback
        selection = self.target_tree.selection()
        if not selection:
            messagebox.showinfo("Edit target", "Select a target to edit.")
            return
        uid = selection[0]
        spec = self._find_spec(uid)
        if spec is None:
            return
        self.target_tree.delete(uid)
        self.target_specs = [item for item in self.target_specs if item.uid != uid]
        self._sync_rake_targets()
        self._update_run_state()
        try:
            index = (
                list(self.df.columns).index(spec.column) if self.df is not None else -1
            )
        except ValueError:
            index = -1
        if index >= 0:
            self.column_list.selection_clear(0, tk.END)
            self.column_list.selection_set(index)
            self.column_list.activate(index)
            self.column_list.see(index)
        self._render_target_editor(spec.column, preset=spec.values)
        self._set_status(f"Editing targets for {spec.column}. Update values and save.")

    # ------------------------------------------------------------------
    def remove_selected_target(self) -> None:  # pragma: no cover - GUI callback
        selection = self.target_tree.selection()
        if not selection:
            messagebox.showinfo("Remove target", "Select a target to remove.")
            return
        uid = selection[0]
        self.target_tree.delete(uid)
        self.target_specs = [item for item in self.target_specs if item.uid != uid]
        self._sync_rake_targets()
        self._update_run_state()
        self._append_log("Removed selected target.")
        self._set_status("Target removed.")

    # ------------------------------------------------------------------
    def clear_all_targets(self) -> None:  # pragma: no cover - GUI callback
        if not self.target_specs:
            return
        if not messagebox.askyesno("Clear targets", "Remove all targets?"):
            return
        self._reset_targets()
        self._append_log("All targets cleared.")
        self._set_status("All targets cleared.")

    # ------------------------------------------------------------------
    def _find_spec(self, uid: str) -> Optional[TargetSpec]:
        for spec in self.target_specs:
            if spec.uid == uid:
                return spec
        return None

    # ------------------------------------------------------------------
    def _reset_targets(self) -> None:
        self.target_specs.clear()
        self.targets.clear()
        for item in self.target_tree.get_children():
            self.target_tree.delete(item)
        self._clear_target_editor()
        self._update_run_state()

    # ------------------------------------------------------------------
    def _sync_rake_targets(self) -> None:
        self.targets = [spec.as_rake_target() for spec in self.target_specs]

    # ------------------------------------------------------------------
    def save_targets(self) -> None:  # pragma: no cover - GUI callback
        if not self.target_specs:
            messagebox.showinfo("Save scheme", "Add at least one target first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        payload = {
            "weight_column": self.weight_column_var.get().strip(),
            "targets": [
                {
                    "column": spec.column,
                    "values": spec.values,
                    "original_total": spec.original_total,
                }
                for spec in self.target_specs
            ],
        }
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError as err:
            messagebox.showerror("Save error", str(err))
            return
        self._append_log(f"Target scheme saved to {path}.")
        self._set_status("Target scheme saved.")

    # ------------------------------------------------------------------
    def load_targets(self) -> None:  # pragma: no cover - GUI callback
        if self.df is None:
            messagebox.showinfo(
                "Load scheme", "Load a dataset before importing targets."
            )
            return
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as err:
            messagebox.showerror("Load error", str(err))
            return
        targets = payload.get("targets", [])
        if not isinstance(targets, list):
            messagebox.showerror("Load error", "Invalid target scheme format.")
            return
        loaded = 0
        for item in targets:
            column = item.get("column")
            values = item.get("values", {})
            original_total = item.get(
                "original_total",
                sum(values.values()) if isinstance(values, dict) else 0,
            )
            if column not in self.df.columns:
                self._append_log(f"Skipped target for unknown column '{column}'.")
                continue
            try:
                normalised, _ = parse_target_inputs(
                    {k: str(v) for k, v in values.items()}
                )
            except ValueError as err:
                self._append_log(f"Skipped target for {column}: {err}")
                continue
            spec = TargetSpec(
                column=column, values=normalised, original_total=original_total
            )
            self._remove_existing_spec_for_column(column)
            self._store_spec(spec)
            loaded += 1
        if "weight_column" in payload and payload["weight_column"]:
            self.weight_column_var.set(str(payload["weight_column"]))
        self._set_status(f"Loaded {loaded} target(s) from scheme.")
        self._append_log(f"Target scheme loaded from {path}.")

    # ------------------------------------------------------------------
    def run_weighting(self) -> None:  # pragma: no cover - GUI callback
        if self.df is None:
            messagebox.showinfo("Run weighting", "Load data before running weighting.")
            return
        if not self.target_specs:
            messagebox.showinfo(
                "Run weighting", "Add at least one target before running weighting."
            )
            return
        weight_column = self.weight_column_var.get().strip()
        if not weight_column:
            messagebox.showinfo("Run weighting", "Specify a weight column name.")
            return
        if weight_column in self.df.columns:
            overwrite = messagebox.askyesno(
                "Overwrite weight column",
                f"Column '{weight_column}' exists. Overwrite with new weights?",
            )
            if not overwrite:
                self._set_status("Weighting cancelled by user.")
                return
        rake_targets = [spec.as_rake_target() for spec in self.target_specs]
        try:
            rake = Rake(self.df.copy(), rake_targets, weight_column_name=weight_column)
            rake.start()
        except Exception as err:  # pragma: no cover - GUI feedback
            messagebox.showerror("Weighting failed", str(err))
            self._append_log(f"Weighting failed: {err}")
            self._set_status("Weighting failed.")
            return

        summary = (
            rake.report.get("summary", {}) if isinstance(rake.report, dict) else {}
        )
        self._populate_summary(summary)
        self._append_log(
            "Weighting completed successfully.\n"
            + f"Weight column: {weight_column}\n"
            + "Targets:\n"
            + "\n".join(
                f"  - {spec.column}: {format_target_values(spec.values)}"
                for spec in self.target_specs
            )
        )
        self._set_status("Weighting completed successfully.")

    # ------------------------------------------------------------------
    def _populate_summary(self, summary: Dict[str, object]) -> None:
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        if not summary:
            return
        for metric, value in summary.items():
            self.summary_tree.insert("", tk.END, values=(metric, value))

    # ------------------------------------------------------------------
    def _append_log(self, message: str) -> None:
        self.output.configure(state="normal")
        self.output.insert(tk.END, message + "\n")
        self.output.see(tk.END)
        self.output.configure(state="disabled")

    # ------------------------------------------------------------------
    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
        self._update_run_state()

    # ------------------------------------------------------------------
    def _update_run_state(self) -> None:
        weight_name = self.weight_column_var.get().strip()
        state = (
            tk.NORMAL
            if self.df is not None and self.target_specs and weight_name
            else tk.DISABLED
        )
        self.run_button.configure(state=state)


if __name__ == "__main__":  # pragma: no cover - manual execution
    app = RakeGUI()
    app.mainloop()
