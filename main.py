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
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
# ----------------------------------------------------------
# [0] 디자인 테마 (Dark Mode)
# ----------------------------------------------------------
THEME = {
    "app_bg": "#1e1e1e",       # 앱 배경
    "chat_bg": "#252526",      # 채팅창 배경
    "input_bg": "#3e3e42",     # 입력창 배경
    
    "my_bubble": "#0078d4",    # 내 말풍선 (Blue)
    "my_text": "#ffffff",
    
    "other_bubble": "#3e3e42", # 상대 말풍선 (Gray)
    "other_text": "#e0e0e0",
    
    "system_text": "#858585",  # 시스템 메시지
    
    "btn_primary": "#0e639c",
    "btn_danger": "#c53030",
    "btn_pin_active": "#d8a016", # 핀 고정 활성화 (Gold)
    "btn_pin_inactive": "#333333" # 핀 비활성화
}

# ----------------------------------------------------------
# [1] 블록체인 백엔드
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
# [2] GUI & Application
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
        self.root.title("chainChat")  # [수정] 서비스명 변경
        self.root.geometry("750x1200")
        self.root.configure(bg=THEME["app_bg"])
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Data
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
        
        # Floating State
        self.is_floating = False

        if not os.path.exists("downloads"): os.makedirs("downloads")

        self.setup_main_menu()

    def on_closing(self):
        self.running = False
        if self.socket:
            try: self.socket.close()
            except: pass
        self.root.destroy()
        sys.exit(0)

    def clear_screen(self):
        for widget in self.root.winfo_children():
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
        self.root.attributes('-topmost', False) # 초기화 시 플로팅 해제

    def safe_update(self, func, *args):
        self.root.after(0, lambda: func(*args))

    # --- Screen 1: Main Menu ---
    def setup_main_menu(self):
        self.reset_network()
        self.clear_screen()
        self.root.configure(bg=THEME["app_bg"])
        
        frame = tk.Frame(self.root, bg=THEME["app_bg"])
        frame.pack(expand=True)

        # [수정] 서비스명 변경 (chainChat)
        tk.Label(frame, text="chainChat", font=("Consolas", 32, "bold"), bg=THEME["app_bg"], fg=THEME["btn_primary"]).pack(pady=(0, 5))
        tk.Label(frame, text="SECURE & ENCRYPTED", font=("Consolas", 10), bg=THEME["app_bg"], fg="#666").pack(pady=(0, 40))
        
        tk.Label(frame, text="NICKNAME", font=("Consolas", 9, "bold"), bg=THEME["app_bg"], fg="#aaa").pack(anchor="w", padx=40)
        self.entry_nickname = tk.Entry(frame, font=("Malgun Gothic", 12), bg=THEME["input_bg"], fg="white", relief="flat", insertbackground="white")
        self.entry_nickname.pack(fill="x", padx=40, pady=(5, 20), ipady=8)
        
        tk.Button(frame, text="CREATE ROOM", command=self.create_room, bg=THEME["btn_primary"], fg="white", 
                  font=("Consolas", 11, "bold"), relief="flat", height=2).pack(fill="x", padx=40, pady=5)
        
        tk.Button(frame, text="JOIN ROOM", command=self.join_room_screen, bg="#333", fg="white", 
                  font=("Consolas", 11, "bold"), relief="flat", height=2).pack(fill="x", padx=40, pady=5)

    # --- Screen 2: Join ---
    def join_room_screen(self):
        self.nickname = self.entry_nickname.get()
        if not self.nickname: 
            messagebox.showwarning("Alert", "Please enter a nickname.")
            return
        self.clear_screen()
        
        frame = tk.Frame(self.root, bg=THEME["app_bg"])
        frame.pack(expand=True, fill="both", padx=40)

        tk.Label(frame, text="ACCESS CODE", font=("Consolas", 12, "bold"), bg=THEME["app_bg"], fg="#aaa").pack(pady=(100, 20))
        self.entry_link = tk.Entry(frame, font=("Consolas", 12), bg=THEME["input_bg"], fg="white", relief="flat", justify="center", insertbackground="white")
        self.entry_link.pack(fill="x", ipady=8, pady=10)
        
        tk.Button(frame, text="CONNECT", command=self.connect_to_host, bg=THEME["btn_primary"], fg="white", 
                  font=("Consolas", 11, "bold"), relief="flat", height=2).pack(fill="x", pady=10)
        
        tk.Button(frame, text="BACK", command=self.setup_main_menu, bg=THEME["app_bg"], fg="#666", relief="flat").pack(pady=10)

    # --- Screen 3: Chat Room ---
    def setup_chat_room(self, info):
        self.clear_screen()
        self.root.configure(bg=THEME["chat_bg"])
        
        # 1. Header
        header = tk.Frame(self.root, bg=THEME["app_bg"], height=50, padx=15)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        tk.Label(header, text=f"● {info}", bg=THEME["app_bg"], font=("Consolas", 10, "bold"), fg="#cccccc").pack(side="left")
        
        btn_frame = tk.Frame(header, bg=THEME["app_bg"])
        btn_frame.pack(side="right")

        # Floating Toggle (PIN)
        self.btn_pin = tk.Button(btn_frame, text="📌 PIN", command=self.toggle_floating, 
                                 bg=THEME["btn_pin_inactive"], fg="#ccc", font=("Consolas", 9, "bold"), relief="flat", padx=8)
        self.btn_pin.pack(side="left", padx=2)
        
        if self.is_host:
            tk.Button(btn_frame, text="LINK", command=self.copy_link, bg=THEME["btn_primary"], fg="white",
                      font=("Consolas", 9), relief="flat", padx=8).pack(side="left", padx=2)
        
        tk.Button(btn_frame, text="EXIT", command=self.return_to_main, bg=THEME["btn_danger"], fg="white",
                  font=("Consolas", 9), relief="flat", padx=8).pack(side="left", padx=2)

        # 2. Chat Area
        self.chat_area = scrolledtext.ScrolledText(self.root, state='disabled', bg=THEME["chat_bg"], fg="white",
                                                   font=("Malgun Gothic", 10), relief="flat", padx=15, pady=15)
        self.chat_area.pack(fill="both", expand=True)

        # 3. Input Area
        input_area = tk.Frame(self.root, bg=THEME["app_bg"], padx=10, pady=10)
        input_area.pack(fill="x", side="bottom")
        
        tk.Button(input_area, text="+", command=self.send_file_action, bg="#333", fg="white", relief="flat", width=3, font=("Consolas", 12)).pack(side="left", padx=(0, 5))
        
        self.msg_entry = tk.Entry(input_area, font=("Malgun Gothic", 11), bg=THEME["input_bg"], fg="white", relief="flat", insertbackground="white")
        self.msg_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.msg_entry.bind("<Return>", self.send_message)
        
        tk.Button(input_area, text="SEND", command=self.send_message, bg=THEME["btn_primary"], fg="white", relief="flat", padx=15).pack(side="right", padx=(5, 0))

        # Footer
        tk.Button(self.root, text="VIEW LEDGER", command=self.open_ledger_window, bg="#111", fg="#444", font=("Consolas", 8), relief="flat").pack(fill="x", side="bottom")

    def toggle_floating(self):
        self.is_floating = not self.is_floating
        self.root.attributes('-topmost', self.is_floating)
        if self.is_floating:
            self.btn_pin.config(bg=THEME["btn_pin_active"], fg="white")
        else:
            self.btn_pin.config(bg=THEME["btn_pin_inactive"], fg="#ccc")

    def return_to_main(self):
        if messagebox.askyesno("Exit", "Disconnect and leave?"):
            self.setup_main_menu()

    def copy_link(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.my_link)
        messagebox.showinfo("Copied", f"Code: {self.my_link}")

    # --- 메시지 그리기 (오른쪽 정렬 유지) ---
    def _ui_draw_bubble(self, sender, message, is_me, is_system):
        self.chat_area.config(state='normal')
        
        if is_system:
            frame = tk.Frame(self.chat_area, bg=THEME["chat_bg"], pady=5)
            lbl = tk.Label(frame, text=f"--- {message} ---", bg=THEME["chat_bg"], fg=THEME["system_text"], font=("Consolas", 8))
            lbl.pack()
            self.chat_area.window_create(tk.END, window=frame)
            self.chat_area.insert(tk.END, "\n")
            self.chat_area.tag_configure("center", justify='center')
            self.chat_area.tag_add("center", "end-2l", "end-1l")
        else:
            container = tk.Frame(self.chat_area, bg=THEME["chat_bg"], pady=2)
            
            if is_me:
                bubble = tk.Label(container, text=message, bg=THEME["my_bubble"], fg=THEME["my_text"],
                                  font=("Malgun Gothic", 10), padx=12, pady=8, justify="left", wraplength=250)
                bubble.pack(side="right")
                
                self.chat_area.window_create(tk.END, window=container)
                self.chat_area.insert(tk.END, "\n")
                
                self.chat_area.tag_configure("right", justify='right')
                self.chat_area.tag_add("right", "end-2l", "end-1l")
                
            else:
                name_lbl = tk.Label(container, text=sender, bg=THEME["chat_bg"], fg="#888", font=("Consolas", 8))
                name_lbl.pack(anchor="w", padx=2)
                
                bubble = tk.Label(container, text=message, bg=THEME["other_bubble"], fg=THEME["other_text"],
                                  font=("Malgun Gothic", 10), padx=12, pady=8, justify="left", wraplength=250)
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
        
        display_name = textwrap.fill(filename, width=25)
        
        card = tk.Frame(container, bg=card_bg, bd=0)
        if is_me: card.pack(side="right")
        else: card.pack(side="left")
        
        tk.Label(card, text=f"📦\n{display_name}", bg=card_bg, fg="white", 
                 font=("Consolas", 10, "bold"), padx=10, pady=5, justify="left").pack(anchor="w")
        
        if not is_me:
            tk.Button(card, text="DOWNLOAD", command=lambda: self.manual_download(filename), 
                      bg="#444", fg="white", relief="flat", font=("Consolas", 8)).pack(fill="x")

        self.chat_area.window_create(tk.END, window=container)
        self.chat_area.insert(tk.END, "\n")
        
        align = "right" if is_me else "left"
        self.chat_area.tag_configure(align, justify=align)
        self.chat_area.tag_add(align, "end-2l", "end-1l")
        
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')

    # --- 기능 로직 ---
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
        if os.path.getsize(filepath) > 30 * 1024 * 1024:
            messagebox.showwarning("Limit", "Max size: 30MB")
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

    # --- Host ---
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
        buffer = ""
        try:
            while self.running:
                data = c.recv(4096)
                if not data: break
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line: continue
                    try:
                        p = json.loads(line)
                        if p['type'] == 'JOIN':
                            client_name = p['nickname']
                            assigned_id = self.next_user_id
                            self.next_user_id += 1
                            self.safe_send(c, {"type": "WELCOME", "assigned_id": assigned_id})
                            msg = f"'{client_name}' joined."
                            self.mine_and_broadcast("System", 0, msg)
                        elif p['type'] == 'CHAT':
                            self.mine_and_broadcast(p['sender'], p['sender_id'], p['message'])
                        elif p['type'] == 'FILE':
                            self.mine_and_broadcast_file(p['sender'], p['sender_id'], p['filename'], p['content'])
                    except: continue
        except: pass
        finally:
            if c in self.clients: self.clients.remove(c)
            c.close()
            if client_name:
                self.mine_and_broadcast("System", 0, f"'{client_name}' left.")

    # --- Guest ---
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
        buffer = ""
        try:
            while self.running:
                data = self.socket.recv(4096)
                if not data: raise ConnectionResetError()
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
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
        win.geometry("600x400")
        win.configure(bg="#1e1e1e")
        txt = scrolledtext.ScrolledText(win, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        txt.pack(fill='both', expand=True)
        log = ""
        for b in self.my_blockchain.chain:
            log += f"[{b.index}] {b.timestamp} | {b.sender}: {b.message}\nHash: {b.hash}\n{'-'*60}\n"
        txt.insert(tk.END, log)

if __name__ == "__main__":
    root = tk.Tk()
    app = BlockChatApp(root)
    root.mainloop()
