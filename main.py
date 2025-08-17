import tkinter as tk
from tkinter import ttk, messagebox
from bson.objectid import ObjectId
from pymongo import MongoClient
import os
import re

# MongoDB connection (defaults to local server)
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "crud_db")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "students")

class MongoCRUDApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MongoDB CRUD - Students")
        self.geometry("900x600")
        self.resizable(True, True)

        # connect to Mongo
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
            self.client.admin.command("ping")  # validate connection
            self.db = self.client[DB_NAME]
            self.col = self.db[COLLECTION_NAME]
            conn_ok = True
        except Exception as e:
            conn_ok = False
            self.db = None
            self.col = None
            print("Mongo connection failed:", e)

        self._build_ui(conn_ok)
        if conn_ok:
            self.load_records()

    def _build_ui(self, conn_ok: bool):
        # status bar
        status_frame = ttk.Frame(self, padding=8)
        status_frame.pack(fill="x")
        self.status_var = tk.StringVar(value=(
            f"Connected to {MONGODB_URI} • DB: {DB_NAME} • Collection: {COLLECTION_NAME}"
            if conn_ok else
            "MongoDB connection failed. Check MONGODB_URI/DB/collection and try again."
        ))
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left")

        # search bar
        search_frame = ttk.Frame(self, padding=8)
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="Search (Name/Email):").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var, width=40).pack(side="left", padx=6)
        ttk.Button(search_frame, text="Search", command=self.search_records).pack(side="left", padx=2)
        ttk.Button(search_frame, text="Show All", command=self.load_records).pack(side="left", padx=2)

        # form
        form = ttk.LabelFrame(self, text="Student Details", padding=8)
        form.pack(fill="x", padx=8, pady=(0,8))

        self.selected_id = None

        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(form, text="Email:").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.email_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.email_var, width=40).grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(form, text="Age:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.age_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.age_var, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        # buttons
        btns = ttk.Frame(self, padding=8)
        btns.pack(fill="x")
        ttk.Button(btns, text="Add", command=self.add_record).pack(side="left", padx=4)
        ttk.Button(btns, text="Update", command=self.update_record).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete", command=self.delete_record).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear", command=self.clear_form).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh", command=self.load_records).pack(side="left", padx=4)

        # table
        table_frame = ttk.Frame(self, padding=8)
        table_frame.pack(fill="both", expand=True)
        columns = ("_id", "name", "email", "age")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("_id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("email", text="Email")
        self.tree.heading("age", text="Age")
        self.tree.column("_id", width=250, anchor="w")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("email", width=250, anchor="w")
        self.tree.column("age", width=60, anchor="center")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    # === CRUD helpers ===
    def validate_form(self):
        name = self.name_var.get().strip()
        email = self.email_var.get().strip()
        age_str = self.age_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Name is required.")
            return None
        if not email or "@" not in email:
            messagebox.showwarning("Validation", "Valid Email is required.")
            return None
        if not age_str.isdigit():
            messagebox.showwarning("Validation", "Age must be a positive integer.")
            return None
        age = int(age_str)
        if age <= 0:
            messagebox.showwarning("Validation", "Age must be > 0.")
            return None
        return {"name": name, "email": email, "age": age}

    def clear_form(self):
        self.selected_id = None
        self.name_var.set("")
        self.email_var.set("")
        self.age_var.set("")
        self.tree.selection_remove(self.tree.selection())

    def on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")  # (_id, name, email, age)
        self.selected_id = values[0]
        self.name_var.set(values[1])
        self.email_var.set(values[2])
        self.age_var.set(values[3])

    def load_records(self):
        if self.col is None:
            messagebox.showerror("MongoDB", "Not connected to MongoDB.")
            return
        self.tree.delete(*self.tree.get_children())
        try:
            for doc in self.col.find().sort("_id", -1):
                self.tree.insert("", "end", values=(str(doc.get("_id")), doc.get("name",""), doc.get("email",""), doc.get("age","")))
        except Exception as e:
            messagebox.showerror("MongoDB", f"Failed to load records: {e}")

    def search_records(self):
        if self.col is None:
            return
        q = self.search_var.get().strip()
        self.tree.delete(*self.tree.get_children())
        try:
            if q:
                regex = {"$regex": re.escape(q), "$options": "i"}
                cursor = self.col.find({"$or": [{"name": regex}, {"email": regex}]})
            else:
                cursor = self.col.find()
            for doc in cursor.sort("_id", -1):
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        str(doc.get("_id")),
                        doc.get("name", ""),
                        doc.get("email", ""),
                        doc.get("age", ""),
                    ),
                )
        except Exception as e:
            messagebox.showerror("MongoDB", f"Search failed: {e}")

    def add_record(self):
        data = self.validate_form()
        if not data or self.col is None:
            return
        try:
            self.col.insert_one(data)
            self.load_records()
            self.clear_form()
            messagebox.showinfo("Success", "Record added.")
        except Exception as e:
            messagebox.showerror("MongoDB", f"Insert failed: {e}")

    def update_record(self):
        if not self.selected_id:
            messagebox.showwarning("Update", "Select a record to update.")
            return
        data = self.validate_form()
        if not data or self.col is None:
            return
        try:
            self.col.update_one({"_id": ObjectId(self.selected_id)}, {"$set": data})
            self.load_records()
            messagebox.showinfo("Success", "Record updated.")
        except Exception as e:
            messagebox.showerror("MongoDB", f"Update failed: {e}")

    def delete_record(self):
        if not self.selected_id:
            messagebox.showwarning("Delete", "Select a record to delete.")
            return
        if self.col is None:
            return
        if not messagebox.askyesno("Confirm", "Delete selected record?"):
            return
        try:
            self.col.delete_one({"_id": ObjectId(self.selected_id)})
            self.load_records()
            self.clear_form()
            messagebox.showinfo("Success", "Record deleted.")
        except Exception as e:
            messagebox.showerror("MongoDB", f"Delete failed: {e}")

if __name__ == "__main__":
    app = MongoCRUDApp()
    app.mainloop()
