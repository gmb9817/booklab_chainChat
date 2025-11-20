import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import socket
import threading
import json
import hashlib
import time
import base64
import os
import sys
import textwrap
import platform 

# ----------------------------------------------------------
# [0] OS 감지 및 환경 설정
# ----------------------------------------------------------
SYSTEM_OS = platform.system()
IS_MAC = (SYSTEM_OS == "Darwin")
IS_WINDOWS = (SYSTEM_OS == "Windows")

# 폰트 설정
if IS_MAC:
    FONT_MAIN = "Apple SD Gothic Neo" 
    FONT_MONO = "Menlo"
else:
    FONT_MAIN = "Malgun Gothic"
    FONT_MONO = "Consolas"

if IS_WINDOWS:
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: pass

# ----------------------------------------------------------
# [1] 디자인 테마
# ----------------------------------------------------------
THEME = {
    "app_bg": "#1e1e1e",        
    "chat_bg": "#252526",       
    "input_bg": "#3e3e42",      
    "my_bubble": "#0078d4",     
    "my_text": "#ffffff",
    "other_bubble": "#3e3e42", 
    "other_text": "#e0e0e0",
    "system_text": "#858585",   
    "btn_primary": "#0e639c",
    "btn_danger": "#c53030",
    "btn_pin_active": "#d8a016",
    "btn_pin_inactive": "#333333"
}

# ----------------------------------------------------------
# [2] 블록체인 백엔드
# ----------------------------------------------------------
class Block:
    def __init__(self, index, timestamp, sender, sender_id, message, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.sender = sender
        self.sender_id = sender_id
        self.message = message
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "sender": self.sender,
            "sender_id": self.sender_id,
            "message": self.message,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "2024-01-01", "System", 0, "Genesis Block", "0")

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_block):
        if new_block.previous_hash != self.get_latest_block().hash: return False
        if new_block.calculate_hash() != new_block.hash: return False
        self.chain.append(new_block)
        return True
     
    def replace_chain(self, new_chain_data):
        temp_chain = []
        for b_data in new_chain_data:
            block = Block(
                b_data['index'], b_data['timestamp'],
                b_data['sender'], b_data['sender_id'],
                b_data['message'],
                b_data['previous_hash']
            )
            block.hash = b_data['hash']
            temp_chain.append(block)
        self.chain = temp_chain
        return True

# ----------------------------------------------------------
# [3] GUI & Application
# ----------------------------------------------------------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "127.0.0.1"

class BlockChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("chainChat")
        self.root.geometry("800x1000") 
        self.root.configure(bg=THEME["app_bg"])
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # [Mac Fix] 메뉴바 + 강제 단축키 + 우클릭 메뉴
        if IS_MAC:
            self.setup_mac_menu()
            self.force_mac_shortcuts()

        self.root.after(500, self.apply_capture_protection)
        
        self.my_blockchain = Blockchain()
        self.socket = None
        self.is_host = False
        self.clients = [] 
        self.nickname = ""
        self.target_port = 9999
        self.my_link = ""
        self.my_id = None
        self.next_user_id = 1 
        self.file_cache = {}
        self.running = True 
        self.is_floating = False

        if not os.path.exists("downloads"): os.makedirs("downloads")
        self.setup_main_menu()

    # ----------------------------------------------------------
    # [Mac Shortcut Fix] 메뉴바 및 단축키 로직 강화
    # ----------------------------------------------------------
    def setup_mac_menu(self):
        """Mac 상단 메뉴바 생성"""
        menubar = tk.Menu(self.root)
        app_menu = tk.Menu(menubar, tearoff=0)
        app_menu.add_command(label="About chainChat")
        app_menu.add_separator()
        app_menu.add_command(label="Quit", command=self.on_closing)
        menubar.add_cascade(label="App", menu=app_menu)
        
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Cmd+Z", command=lambda: self.root.focus_get().event_generate("<<Undo>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Cmd+X", command=lambda: self.root.focus_get().event_generate("<<Cut>>"))
        edit_menu.add_command(label="Copy", accelerator="Cmd+C", command=lambda: self.root.focus_get().event_generate("<<Copy>>"))
        edit_menu.add_command(label="Paste", accelerator="Cmd+V", command=lambda: self.root.focus_get().event_generate("<<Paste>>"))
        edit_menu.add_command(label="Select All", accelerator="Cmd+A", command=lambda: self.root.focus_get().event_generate("<<SelectAll>>"))
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        self.root.config(menu=menubar)

    def force_mac_shortcuts(self):
        """Mac 키보드 이벤트 강제 바인딩"""
        def cmd_action(event, action_key):
            widget = self.root.focus_get()
            if widget:
                try:
                    if action_key == 'c': widget.event_generate("<<Copy>>")
                    elif action_key == 'v': widget.event_generate("<<Paste>>")
                    elif action_key == 'x': widget.event_generate("<<Cut>>")
                    elif action_key == 'a': widget.event_generate("<<SelectAll>>")
                except: pass
            return "break"

        self.root.bind("<Command-c>", lambda e: cmd_action(e, 'c'))
        self.root.bind("<Command-v>", lambda e: cmd_action(e, 'v'))
        self.root.bind("<Command-x>", lambda e: cmd_action(e, 'x'))
        self.root.bind("<Command-a>", lambda e: cmd_action(e, 'a'))

    def show_context_menu(self, event):
        try:
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Cut", command=lambda: self.root.focus_get().event_generate("<<Cut>>"))
            menu.add_command(label="Copy", command=lambda: self.root.focus_get().event_generate("<<Copy>>"))
            menu.add_command(label="Paste", command=lambda: self.root.focus_get().event_generate("<<Paste>>"))
            menu.tk_popup(event.x_root, event.y_root)
        except: pass

    def bind_right_click(self, widget):
        if IS_MAC:
            widget.bind("<Button-2>", self.show_context_menu)
            widget.bind("<Button-3>", self.show_context_menu)
        else:
            widget.bind("<Button-3>", self.show_context_menu)

    # ----------------------------------------------------------
    # 기존 기능들
    # ----------------------------------------------------------
    def apply_capture_protection(self):
        if IS_MAC:
            try:
                from AppKit import NSApplication, NSWindowSharingNone
                app = NSApplication.sharedApplication()
                for window in app.windows():
                    window.setSharingType_(NSWindowSharingNone)
            except: pass 
        elif IS_WINDOWS:
            try:
                import ctypes
                WDA_EXCLUDEFROMCAPTURE = 17 
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if hwnd == 0: hwnd = self.root.winfo_id()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            except: pass

    def on_closing(self):
        self.running = False
        if self.socket:
            try: self.socket.close()
            except: pass
        self.root.destroy()
        sys.exit(0)

    def clear_screen(self):
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Menu): continue 
            widget.destroy()

    def reset_network(self):
        self.running = False
        if self.socket:
            try: self.socket.close()
            except: pass
        self.socket = None
        self.clients = []
        self.my_blockchain = Blockchain()
        self.is_host = False
        self.root.attributes('-topmost', False)

    def safe_update(self, func, *args):
        self.root.after(0, lambda: func(*args))

    def create_button(self, parent, text, command, bg=THEME["btn_primary"], hover_bg="#1177bb", width=None, height=None):
        if IS_MAC:
            btn = tk.Label(parent, text=text, bg=bg, fg="white", 
                           font=(FONT_MONO, 12, "bold"), cursor="pointinghand")
            btn.bind("<Button-1>", lambda e: command())
            def on_enter(e): btn.config(bg=hover_bg)
            def on_leave(e): btn.config(bg=bg)
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            btn.config(pady=10) 
            return btn
        else:
            btn = tk.Button(parent, text=text, command=command, 
                            bg=bg, fg="white", font=(FONT_MONO, 10, "bold"), 
                            relief="flat", activebackground=hover_bg, activeforeground="white")
            if width: btn.config(width=width)
            if height: btn.config(height=height)
            btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
            btn.bind("<Leave>", lambda e: btn.config(bg=bg))
            return btn

    def create_entry(self, parent, font_size=12, justify="left"):
        entry = tk.Entry(parent, font=(FONT_MAIN, font_size), bg=THEME["input_bg"], 
                        fg="white", relief="flat", insertbackground="white", 
                        justify=justify, highlightthickness=0)
        self.bind_right_click(entry)
        return entry

    # ----------------------------------------------------------
    # [Screen] Main Menu
    # ----------------------------------------------------------
    def setup_main_menu(self):
        self.reset_network()
        self.clear_screen()
        self.root.configure(bg=THEME["app_bg"])
        
        frame = tk.Frame(self.root, bg=THEME["app_bg"])
        frame.pack(expand=True)

        tk.Label(frame, text="chainChat", font=(FONT_MONO, 48, "bold"), bg=THEME["app_bg"], fg=THEME["btn_primary"]).pack(pady=(0, 5))
        tk.Label(frame, text="SECURE & ENCRYPTED", font=(FONT_MONO, 14), bg=THEME["app_bg"], fg="#666").pack(pady=(0, 60))
        
        tk.Label(frame, text="NICKNAME", font=(FONT_MONO, 11, "bold"), bg=THEME["app_bg"], fg="#aaa").pack(anchor="w", padx=80)
        
        self.entry_nickname = self.create_entry(frame, font_size=14)
        self.entry_nickname.pack(fill="x", padx=80, pady=(5, 30), ipady=10)
        
        btn_frame1 = tk.Frame(frame, bg=THEME["app_bg"])
        btn_frame1.pack(fill="x", padx=80, pady=8)
        btn1 = self.create_button(btn_frame1, "CREATE ROOM", self.create_room)
        btn1.pack(fill="x")

        btn_frame2 = tk.Frame(frame, bg=THEME["app_bg"])
        btn_frame2.pack(fill="x", padx=80, pady=8)
        btn2 = self.create_button(btn_frame2, "JOIN ROOM", self.join_room_screen, bg="#333", hover_bg="#444")
        btn2.pack(fill="x")

    # ----------------------------------------------------------
    # [Screen] Join Room
    # ----------------------------------------------------------
    def join_room_screen(self):
        self.nickname = self.entry_nickname.get()
        if not self.nickname: 
            messagebox.showwarning("Alert", "Please enter a nickname.")
            return
        self.clear_screen()
        
        frame = tk.Frame(self.root, bg=THEME["app_bg"])
        frame.pack(expand=True, fill="both", padx=80)

        tk.Label(frame, text="ACCESS CODE", font=(FONT_MONO, 14, "bold"), bg=THEME["app_bg"], fg="#aaa").pack(pady=(150, 20))
        
        self.entry_link = self.create_entry(frame, font_size=14, justify="center")
        self.entry_link.pack(fill="x", ipady=10, pady=10)
        self.entry_link.focus_set() 
        
        btn_frame1 = tk.Frame(frame, bg=THEME["app_bg"])
        btn_frame1.pack(fill="x", pady=15)
        self.create_button(btn_frame1, "CONNECT", self.connect_to_host).pack(fill="x")

        btn_frame2 = tk.Frame(frame, bg=THEME["app_bg"])
        btn_frame2.pack(fill="x", pady=10)
        self.create_button(btn_frame2, "BACK", self.setup_main_menu, bg=THEME["app_bg"], hover_bg="#333").pack(fill="x")

    # ----------------------------------------------------------
    # [Screen] Chat Room
    # ----------------------------------------------------------
    def setup_chat_room(self, info):
        self.clear_screen()
        self.root.configure(bg=THEME["chat_bg"])
        
        footer = tk.Frame(self.root, bg="#111")
        footer.pack(side="bottom", fill="x")
        f_btn_frame = tk.Frame(footer, bg="#111")
        f_btn_frame.pack(fill="x")
        self.create_button(f_btn_frame, "VIEW LEDGER", self.open_ledger_window, bg="#111", hover_bg="#222").pack(fill="x")

        input_area = tk.Frame(self.root, bg=THEME["app_bg"], padx=15, pady=15)
        input_area.pack(side="bottom", fill="x")
        
        file_btn_frame = tk.Frame(input_area, bg=THEME["app_bg"])
        file_btn_frame.pack(side="left", padx=(0, 10))
        self.create_button(file_btn_frame, " + ", self.send_file_action, bg="#333", hover_bg="#555").pack()
        
        self.msg_entry = self.create_entry(input_area, font_size=12)
        self.msg_entry.pack(side="left", fill="x", expand=True, ipady=8)
        
        # [수정된 부분] Mac에서 한글 입력 시 엔터 두 번 눌러야 하는 문제 해결
        self.msg_entry.bind("<Return>", self.send_message)
        self.msg_entry.bind("<KeyRelease-Return>", self.send_message) 
        
        self.msg_entry.focus_set()
        
        send_btn_frame = tk.Frame(input_area, bg=THEME["app_bg"])
        send_btn_frame.pack(side="right", padx=(10, 0))
        self.create_button(send_btn_frame, "SEND", self.send_message).pack()

        header = tk.Frame(self.root, bg=THEME["app_bg"], height=60, padx=20)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text=f"● {info}", bg=THEME["app_bg"], font=(FONT_MONO, 12, "bold"), fg="#cccccc").pack(side="left")
        
        btn_frame = tk.Frame(header, bg=THEME["app_bg"])
        btn_frame.pack(side="right")

        p_frame = tk.Frame(btn_frame, bg=THEME["app_bg"])
        p_frame.pack(side="left", padx=5)
        self.btn_pin = self.create_button(p_frame, "📌 PIN", self.toggle_floating, bg=THEME["btn_pin_inactive"])
        self.btn_pin.pack()
        
        if self.is_host:
            l_frame = tk.Frame(btn_frame, bg=THEME["app_bg"])
            l_frame.pack(side="left", padx=5)
            self.create_button(l_frame, "LINK", self.copy_link).pack()
        
        e_frame = tk.Frame(btn_frame, bg=THEME["app_bg"])
        e_frame.pack(side="left", padx=5)
        self.create_button(e_frame, "EXIT", self.return_to_main, bg=THEME["btn_danger"], hover_bg="#e53935").pack()

        self.chat_area = scrolledtext.ScrolledText(self.root, state='disabled', bg=THEME["chat_bg"], fg="white",
                                                   font=(FONT_MAIN, 12), relief="flat", padx=20, pady=20, highlightthickness=0)
        self.chat_area.pack(fill="both", expand=True)
        self.bind_right_click(self.chat_area)

    def toggle_floating(self):
        self.is_floating = not self.is_floating
        self.root.attributes('-topmost', self.is_floating)
        
        if IS_WINDOWS: 
            if self.is_floating: self.btn_pin.config(bg=THEME["btn_pin_active"], fg="white")
            else: self.btn_pin.config(bg=THEME["btn_pin_inactive"], fg="#ccc")
        else:
            color = THEME["btn_pin_active"] if self.is_floating else THEME["btn_pin_inactive"]
            txt = "📌 PIN (ON)" if self.is_floating else "📌 PIN"
            self.btn_pin.config(bg=color, text=txt)

    def return_to_main(self):
        if messagebox.askyesno("Exit", "Disconnect and leave?"):
            self.setup_main_menu()

    def copy_link(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.my_link)
        self.root.update() 
        messagebox.showinfo("Copied", f"Code: {self.my_link}")

    def _ui_draw_bubble(self, sender, message, is_me, is_system):
        self.chat_area.config(state='normal')
        
        if is_system:
            frame = tk.Frame(self.chat_area, bg=THEME["chat_bg"], pady=5)
            lbl = tk.Label(frame, text=f"--- {message} ---", bg=THEME["chat_bg"], fg=THEME["system_text"], font=(FONT_MONO, 9))
            lbl.pack()
            self.chat_area.window_create(tk.END, window=frame)
            self.chat_area.insert(tk.END, "\n")
            self.chat_area.tag_configure("center", justify='center')
            self.chat_area.tag_add("center", "end-2l", "end-1l")
        else:
            container = tk.Frame(self.chat_area, bg=THEME["chat_bg"], pady=2)
            
            if is_me:
                bubble = tk.Label(container, text=message, bg=THEME["my_bubble"], fg=THEME["my_text"],
                                  font=(FONT_MAIN, 11), padx=14, pady=10, justify="left", wraplength=400)
                bubble.pack(side="right")
                self.chat_area.window_create(tk.END, window=container)
                self.chat_area.insert(tk.END, "\n")
                self.chat_area.tag_configure("right", justify='right')
                self.chat_area.tag_add("right", "end-2l", "end-1l")
            else:
                name_lbl = tk.Label(container, text=sender, bg=THEME["chat_bg"], fg="#888", font=(FONT_MONO, 9))
                name_lbl.pack(anchor="w", padx=2)
                
                bubble = tk.Label(container, text=message, bg=THEME["other_bubble"], fg=THEME["other_text"],
                                  font=(FONT_MAIN, 11), padx=14, pady=10, justify="left", wraplength=400)
                bubble.pack(anchor="w")
                self.chat_area.window_create(tk.END, window=container)
                self.chat_area.insert(tk.END, "\n")
                self.chat_area.tag_configure("left", justify='left')
                self.chat_area.tag_add("left", "end-2l", "end-1l")

        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')

    def _ui_draw_file(self, filename, sender_name, sender_id):
        self.chat_area.config(state='normal')
        is_me = (sender_id == self.my_id)
        
        container = tk.Frame(self.chat_area, bg=THEME["chat_bg"], pady=5)
        card_bg = THEME["my_bubble"] if is_me else THEME["other_bubble"]
        
        display_name = textwrap.fill(filename, width=30)
        
        card = tk.Frame(container, bg=card_bg, bd=0)
        if is_me: card.pack(side="right")
        else: card.pack(side="left")
        
        tk.Label(card, text=f"📦\n{display_name}", bg=card_bg, fg="white", 
                 font=(FONT_MONO, 11, "bold"), padx=14, pady=8, justify="left").pack(anchor="w")
        
        if not is_me:
            dl_frame = tk.Frame(card, bg=card_bg)
            dl_frame.pack(fill="x")
            self.create_button(dl_frame, "DOWNLOAD", lambda: self.manual_download(filename), 
                                     bg="#444", hover_bg="#555").pack(fill="x")

        self.chat_area.window_create(tk.END, window=container)
        self.chat_area.insert(tk.END, "\n")
        
        align = "right" if is_me else "left"
        self.chat_area.tag_configure(align, justify=align)
        self.chat_area.tag_add(align, "end-2l", "end-1l")
        
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')

    def manual_download(self, filename):
        if filename not in self.file_cache:
            messagebox.showerror("Error", "File expired or not found.")
            return
        save_path = filedialog.asksaveasfilename(initialfile=filename)
        if save_path:
            try:
                with open(save_path, "wb") as f: f.write(base64.b64decode(self.file_cache[filename]))
                messagebox.showinfo("Success", "File Saved.")
            except Exception as e: messagebox.showerror("Error", str(e))

    def send_file_action(self):
        filepath = filedialog.askopenfilename()
        if not filepath: return
        filename = os.path.basename(filepath)
        if os.path.getsize(filepath) > 50 * 1024 * 1024:
            messagebox.showwarning("Limit", "Max size: 50MB")
            return
        try:
            with open(filepath, "rb") as f: encoded = base64.b64encode(f.read()).decode('utf-8')
            self.file_cache[filename] = encoded
            if self.is_host: self.mine_and_broadcast_file(self.nickname, self.my_id, filename, encoded)
            else: self.safe_send(self.socket, {
                "type": "FILE", "sender": self.nickname, "sender_id": self.my_id, "filename": filename, "content": encoded
            })
        except Exception as e: messagebox.showerror("Error", str(e))

    def mine_and_broadcast_file(self, sender, sender_id, filename, encoded):
        self.file_cache[filename] = encoded
        log_msg = f"FILE_TRANSFER:{filename}" 
        last = self.my_blockchain.get_latest_block()
        new_block = Block(last.index+1, time.ctime(), sender, sender_id, log_msg, last.hash)
        if self.my_blockchain.add_block(new_block):
            self.safe_update(self.display_block, new_block)
            packet = {"type": "FILE_RECV", "sender": sender, "sender_id": sender_id, "filename": filename, "content": encoded, "block_data": new_block.__dict__}
            for c in self.clients: self.safe_send(c, packet)

    def safe_send(self, sock, data):
        try:
            packet = (json.dumps(data) + "\n").encode('utf-8')
            sock.sendall(packet)
        except: pass

    def create_room(self):
        self.nickname = self.entry_nickname.get()
        if not self.nickname: return
        self.is_host = True
        self.my_id = 1
        self.next_user_id = 2 
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        while True:
            try: self.socket.bind(('0.0.0.0', self.target_port)); break
            except OSError: self.target_port += 1
        self.socket.listen(5)
        self.my_link = f"{get_local_ip()}:{self.target_port}"
        self.setup_chat_room(f"HOST | {self.nickname}")
        self.safe_update(self._ui_draw_bubble, "System", "Room Created", False, True)
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while self.running:
            try:
                c, a = self.socket.accept()
                self.clients.append(c)
                self.safe_send(c, {"type": "SYNC", "chain": [b.__dict__ for b in self.my_blockchain.chain]})
                threading.Thread(target=self.handle_client, args=(c,), daemon=True).start()
            except: break

    def handle_client(self, c):
        client_name = None
        try:
            while self.running:
                data = c.recv(4096)
                if not data: break
                buffer = data.decode('utf-8')
                for line in buffer.split("\n"):
                    if not line: continue
                    try:
                        p = json.loads(line)
                        if p['type'] == 'JOIN':
                            client_name = p['nickname']
                            assigned_id = self.next_user_id
                            self.next_user_id += 1
                            self.safe_send(c, {"type": "WELCOME", "assigned_id": assigned_id})
                            self.mine_and_broadcast("System", 0, f"'{client_name}' joined.")
                        elif p['type'] == 'CHAT':
                            self.mine_and_broadcast(p['sender'], p['sender_id'], p['message'])
                        elif p['type'] == 'FILE':
                            self.mine_and_broadcast_file(p['sender'], p['sender_id'], p['filename'], p['content'])
                    except: continue
        except: pass
        finally:
            if c in self.clients: self.clients.remove(c)
            c.close()
            if client_name: self.mine_and_broadcast("System", 0, f"'{client_name}' left.")

    def connect_to_host(self):
        link = self.entry_link.get()
        if not link: return
        try:
            ip, port = link.split(':')
            self.running = True
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((ip, int(port)))
            self.is_host = False
            self.setup_chat_room(f"GUEST | {self.nickname}")
            self.safe_send(self.socket, {"type": "JOIN", "nickname": self.nickname})
            threading.Thread(target=self.receive, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"{e}")
            self.setup_main_menu()

    def receive(self):
        try:
            while self.running:
                data = self.socket.recv(4096)
                if not data: raise ConnectionResetError()
                buffer = data.decode('utf-8')
                for line in buffer.split("\n"):
                    if not line: continue
                    try:
                        p = json.loads(line)
                        if p['type'] == 'WELCOME':
                            self.my_id = p['assigned_id']
                            self.safe_update(self._ui_draw_bubble, "System", "Connected.", False, True)
                        elif p['type'] == 'SYNC':
                            if self.my_blockchain.replace_chain(p['chain']):
                                self.safe_update(self._ui_draw_bubble, "System", "History Synced.", False, True)
                                for b in self.my_blockchain.chain[1:]: 
                                    self.safe_update(self.display_block, b)
                        elif p['type'] == 'BLOCK':
                            b = p['data']
                            new_b = Block(b['index'], b['timestamp'], b['sender'], b['sender_id'], b['message'], b['previous_hash'])
                            new_b.hash = b['hash']
                            if self.my_blockchain.add_block(new_b): 
                                self.safe_update(self.display_block, new_b)
                        elif p['type'] == 'FILE_RECV':
                            self.file_cache[p['filename']] = p['content']
                            b = p['block_data']
                            new_b = Block(b['index'], b['timestamp'], b['sender'], b['sender_id'], b['message'], b['previous_hash'])
                            new_b.hash = b['hash']
                            if self.my_blockchain.add_block(new_b): 
                                self.safe_update(self.display_block, new_b)
                    except: continue
        except:
            if self.running:
                self.running = False
                self.safe_update(messagebox.showwarning, "Info", "Connection Closed")
                self.safe_update(self.setup_main_menu)

    def send_message(self, e=None):
        msg = self.msg_entry.get()
        if not msg: return
        self.msg_entry.delete(0, tk.END)
        if self.my_id is None: return
        
        if self.is_host: self.mine_and_broadcast(self.nickname, self.my_id, msg)
        else: self.safe_send(self.socket, {"type": "CHAT", "sender": self.nickname, "sender_id": self.my_id, "message": msg})

    def mine_and_broadcast(self, sender, sender_id, msg):
        last = self.my_blockchain.get_latest_block()
        new_b = Block(last.index+1, time.ctime(), sender, sender_id, msg, last.hash)
        if self.my_blockchain.add_block(new_b):
            self.safe_update(self.display_block, new_b)
            for c in self.clients: self.safe_send(c, {"type": "BLOCK", "data": new_b.__dict__})

    def display_block(self, block):
        if block.message.startswith("FILE_TRANSFER:") or block.message.startswith("📎"):
            filename = block.message.replace("FILE_TRANSFER:", "").replace("📎 파일 전송: ", "")
            self._ui_draw_file(filename, block.sender, block.sender_id)
            return
        
        if block.sender == "System":
            self._ui_draw_bubble("System", block.message, False, True)
        else:
            is_me = (block.sender_id == self.my_id)
            self._ui_draw_bubble(block.sender, block.message, is_me, False)

    def open_ledger_window(self):
        win = tk.Toplevel(self.root)
        win.title("Blockchain Ledger")
        win.geometry("800x600")
        win.configure(bg="#1e1e1e")
        txt = scrolledtext.ScrolledText(win, bg="#1e1e1e", fg="#00ff00", font=(FONT_MONO, 10))
        txt.pack(fill='both', expand=True)
        log = ""
        for b in self.my_blockchain.chain:
            log += f"[{b.index}] {b.timestamp} | {b.sender}: {b.message}\nHash: {b.hash}\n{'-'*60}\n"
        txt.insert(tk.END, log)

if __name__ == "__main__":
    root = tk.Tk()
    app = BlockChatApp(root)
    root.mainloop()
