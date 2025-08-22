import requests
import json
import time
import os
import threading
from telegram import InputFile, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, render_template_string, jsonify
from datetime import datetime, timezone, timedelta

# --- Konfigurasi ---
WIB = timezone(timedelta(hours=7))
url = "https://indodax.com/api/v2/chatroom/history"
jsonl_file = "chat_indodax.jsonl"
request_file = "last_request.json"
TOKEN = os.environ.get("TOKEN", "")  # Ganti dengan token bot kamu

# --- Polling Chat Indodax ---
def polling_chat():
    seen_ids = set()
    print("Polling chat Indodax aktif... (Ctrl+C untuk berhenti)")
    while True:
        try:
            response = requests.get(url)
            data = response.json()
            if data.get("success"):
                chat_list = data["data"]["content"]
                new_chats = []
                for chat in chat_list:
                    if chat['id'] not in seen_ids:
                        seen_ids.add(chat['id'])
                        chat_time_utc = datetime.fromtimestamp(chat["timestamp"], tz=timezone.utc)
                        chat_time_wib = chat_time_utc.astimezone(WIB)
                        chat["timestamp_wib"] = chat_time_wib.strftime('%Y-%m-%d %H:%M:%S')
                        new_chats.append(chat)
                if new_chats:
                    with open(jsonl_file, "a", encoding="utf-8") as f:
                        for chat in new_chats:
                            f.write(json.dumps(chat, ensure_ascii=False) + "\n")
                    print(f"{len(new_chats)} chat baru disimpan.")
                else:
                    print("Tidak ada chat baru.")
            else:
                print("Gagal mengambil data dari API.")
        except Exception as e:
            print(f"Error polling chat: {e}")
        time.sleep(1)  # polling setiap 1 detik

# --- Bot Telegram ---
def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")

async def rank_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 4:
        await update.message.reply_text("Format: /rank_all YYYY-MM-DD HH:MM YYYY-MM-DD HH:MM")
        return
    t_awal = context.args[0] + " " + context.args[1]
    t_akhir = context.args[2] + " " + context.args[3]
    # Simpan request ke file
    with open(request_file, "w", encoding="utf-8") as f:
        json.dump({"start": t_awal, "end": t_akhir}, f)
    await update.message.reply_text("Permintaan diterima! Silakan cek website untuk hasilnya.")

async def rank_berdasarkan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 5:
        await update.message.reply_text("Format: /rank_berdasarkan <kata> YYYY-MM-DD HH:MM YYYY-MM-DD HH:MM")
        return
    kata = context.args[0].lower()
    t_awal = context.args[1] + " " + context.args[2]
    t_akhir = context.args[3] + " " + context.args[4]
    with open(request_file, "w", encoding="utf-8") as f:
        json.dump({"start": t_awal, "end": t_akhir, "kata": kata}, f)
    await update.message.reply_text(f"Permintaan ranking berdasarkan kata '{kata}' diterima! Silakan cek website untuk hasilnya.")

async def reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if os.path.exists(request_file):
            os.remove(request_file)
        await update.message.reply_text("Tampilan website sudah direset. Data chat masih aman.")
    except Exception as e:
        await update.message.reply_text(f"Gagal reset tampilan: {e}")
        
async def reset_2025(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if os.path.exists("chat_indodax.jsonl"):
            os.remove("chat_indodax.jsonl")
        await update.message.reply_text("Data chat pada file chat_indodax.jsonl berhasil direset (dihapus).")
    except Exception as e:
        await update.message.reply_text(f"Gagal reset data chat: {e}")
        
# --- /export_all ---
async def export_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("chat_indodax.jsonl", "rb") as f:
            await update.message.reply_document(document=InputFile(f, filename="chat_indodax.jsonl"))
    except Exception as e:
        await update.message.reply_text(f"Gagal mengirim file: {e}")

# --- /export_waktu <awal> <akhir> ---
async def export_waktu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 4:
        await update.message.reply_text("Format: /export_waktu YYYY-MM-DD HH:MM YYYY-MM-DD HH:MM")
        return
    waktu_awal = context.args[0] + " " + context.args[1]
    waktu_akhir = context.args[2] + " " + context.args[3]
    try:
        from datetime import datetime
        t_awal = datetime.strptime(waktu_awal, "%Y-%m-%d %H:%M")
        t_akhir = datetime.strptime(waktu_akhir, "%Y-%m-%d %H:%M")
        hasil = []
        with open("chat_indodax.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                chat = json.loads(line)
                t_chat = datetime.strptime(chat["timestamp_wib"], "%Y-%m-%d %H:%M:%S")
                if t_awal <= t_chat <= t_akhir:
                    hasil.append(chat)
        if not hasil:
            await update.message.reply_text("Tidak ada data pada rentang waktu tersebut.")
            return
        # Simpan hasil filter ke file sementara
        temp_file = "chat_indodax_filtered.jsonl"
        with open(temp_file, "w", encoding="utf-8") as f:
            for chat in hasil:
                f.write(json.dumps(chat, ensure_ascii=False) + "\n")
        with open(temp_file, "rb") as f:
            await update.message.reply_document(document=InputFile(f, filename=temp_file))
        os.remove(temp_file)
    except Exception as e:
        await update.message.reply_text(f"Gagal export data: {e}")

async def rank_berdasarkan_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 5:
        await update.message.reply_text("Format: /rank_berdasarkan_username <username1> <username2> ... YYYY-MM-DD HH:MM YYYY-MM-DD HH:MM")
        return
    usernames = context.args[:-4]
    t_awal = context.args[-4] + " " + context.args[-3]
    t_akhir = context.args[-2] + " " + context.args[-1]
    # Simpan permintaan ke file
    with open("last_request.json", "w", encoding="utf-8") as f:
        json.dump({
            "usernames": usernames,
            "start": t_awal,
            "end": t_akhir,
            "mode": "username"
        }, f)
    await update.message.reply_text("Permintaan ranking berdasarkan username diterima! Silakan cek website untuk hasilnya.")

# --- Flask App ---
app = Flask(__name__)

def get_ranking():
    try:
        with open("last_request.json", "r", encoding="utf-8") as f:
            req = json.load(f)
        t_awal = datetime.strptime(req["start"], "%Y-%m-%d %H:%M")
        t_akhir = datetime.strptime(req["end"], "%Y-%m-%d %H:%M")
        usernames = [u.lower() for u in req.get("usernames", [])]
        mode = req.get("mode", "")
        kata = req.get("kata", None)
    except Exception as e:
        return [], "Tidak ada DATA", "", "", []

    user_info = {}
    try:
        with open("chat_indodax.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                chat = json.loads(line)
                t_chat = datetime.strptime(chat["timestamp_wib"], "%Y-%m-%d %H:%M:%S")
                uname = chat["username"].lower()
                # --- FILTER WAKTU ---
                if not (t_awal <= t_chat <= t_akhir):
                    continue
                # --- FILTER KATA (CONTENT) ---
                if kata and kata not in chat["content"].lower():
                    continue
                # --- FILTER USERNAME (JIKA MODE USERNAME) ---
                if mode == "username" and usernames:
                    if uname not in usernames:
                        continue
                # --- OLAH DATA USER ---
                if uname not in user_info:
                    user_info[uname] = {
                        "count": 1,
                        "last_content": chat["content"],
                        "last_time": chat["timestamp_wib"]
                    }
                else:
                    user_info[uname]["count"] += 1
                    if t_chat > datetime.strptime(user_info[uname]["last_time"], "%Y-%m-%d %H:%M:%S"):
                        user_info[uname]["last_content"] = chat["content"]
                        user_info[uname]["last_time"] = chat["timestamp_wib"]
    except Exception as e:
        return [], "Tidak ada DATA", "", "", []

    if mode == "username" and usernames:
        ranking = [(u, user_info[u]) if u in user_info else (u, {"count": 0, "last_content": "-", "last_time": "-"}) for u in usernames]
    else:
        ranking = sorted(user_info.items(), key=lambda x: x[1]["count"], reverse=True)
    return ranking, None, req["start"], req["end"], usernames

@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ranking Chat Indodax</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>
        <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 30px; }
            table.dataTable thead th { font-weight: bold; }
        </style>
    </head>
    <body>
    <h2>Top Chatroom Indodax</h2>
    <table id="ranking" class="display" style="width:100%">
        <thead>
        <tr>
            <th width="1%">Nomor</th>
            <th width="10%">Username</th>
            <th width="1%">Jumlah</th>
            <th style="text-align: center;" width="50%">Terakhir Chat</th>
            <th width="20%">Waktu Chat</th>
        </tr>
        </thead>
        <tbody>
        </tbody>
    </table>
    <p id="periode"></p>
    <script>
        var table = $('#ranking').DataTable({
            "order": [[2, "desc"]],
            "paging": false,
            "info": false,
            "searching": true,
            "language": {
            "emptyTable": "Tidak ada DATA"
            }
        });

        function loadData() {
            $.getJSON("/data", function(data) {
                table.clear();
                if (data.ranking.length === 0) {
                    $("#periode").html("<b>Tidak ada DATA</b>");
                    table.draw();
                    return;
                }
                for (var i = 0; i < data.ranking.length; i++) {
                    var row = data.ranking[i];
                    table.row.add([
                        i+1,
                        row.username,
                        row.count,
                        row.last_content,
                        row.last_time
                    ]);
                }
                table.draw();
                $("#periode").html("Periode: <b>" + data.t_awal + "</b> s/d <b>" + data.t_akhir + "</b>");
            });
        }

        loadData();
        setInterval(loadData, 1000); // refresh setiap 1 detik
    </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/data")
def data():
    ranking, error, t_awal, t_akhir, usernames = get_ranking()
    if error or not ranking:
        return jsonify({"error": "Tidak ada DATA", "ranking": [], "t_awal": "", "t_akhir": ""})
    data = []
    for user, info in ranking:
        data.append({
            "username": user,
            "count": info["count"],
            "last_content": info["last_content"],
            "last_time": info["last_time"]
        })
    return jsonify({
        "ranking": data,
        "t_awal": t_awal,
        "t_akhir": t_akhir
    })

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

# --- Main ---
if __name__ == "__main__":
    # Jalankan polling chat di thread terpisah
    t1 = threading.Thread(target=polling_chat, daemon=True)
    t1.start()

    # Jalankan Flask di thread terpisah
    t2 = threading.Thread(target=run_flask, daemon=True)
    t2.start()

    # Jalankan bot Telegram di main thread
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("rank_all", rank_all))
    app.add_handler(CommandHandler("rank_berdasarkan", rank_berdasarkan))
    app.add_handler(CommandHandler("reset_data", reset_data))
    app.add_handler(CommandHandler("reset_2025", reset_2025))
    app.add_handler(CommandHandler("export_all", export_all))
    app.add_handler(CommandHandler("export_waktu", export_waktu))
    app.add_handler(CommandHandler("rank_berdasarkan_username", rank_berdasarkan_username))
    print("Bot Telegram aktif...")
    app.run_polling()
