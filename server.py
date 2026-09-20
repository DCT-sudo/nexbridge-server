from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import google.generativeai as genai
import os
import qrcode
import socket

app = Flask(__name__)
CORS(app)

# API KEY BURAYA
GEMINI_API_KEY = "AQ.Ab8RN6L5rScbW6du-7FeByuPJlCsNZkMneAUyjt-U_CYTYc6Cw"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

@app.route("/komut", methods=["POST"])
def komut():
    data = request.json
    mesaj = data.get("mesaj", "")
    
    sistem = """Sen bir dosya asistanısın. Kullanıcı senden dosya göndermesini veya almasını isteyebilir.
    Eğer dosya isteği varsa JSON formatında yanıt ver:
    {"islem": "gonder", "dosya": "dosya_adi.txt"}
    veya
    {"islem": "al", "dosya": "dosya_adi.txt"}
    Yoksa normal yanıt ver."""
    
    yanit = model.generate_content(sistem + "\n\nKullanıcı: " + mesaj)
    return jsonify({"yanit": yanit.text})

@app.route("/dosya/gonder/<dosya_adi>", methods=["GET"])
def dosya_gonder(dosya_adi):
    yol = os.path.join(os.path.expanduser("~"), "Desktop", dosya_adi)
    if os.path.exists(yol):
        return send_file(yol, as_attachment=True)
    return jsonify({"hata": "Dosya bulunamadı"}), 404

@app.route("/dosya/al", methods=["POST"])
def dosya_al():
    if "dosya" not in request.files:
        return jsonify({"hata": "Dosya yok"}), 400
    dosya = request.files["dosya"]
    kayit_yolu = os.path.join(os.path.expanduser("~"), "Desktop", dosya.filename)
    dosya.save(kayit_yolu)
    return jsonify({"mesaj": f"{dosya.filename} masaüstüne kaydedildi!"})

@app.route("/qr")
def qr():
    ip = get_local_ip()
    url = f"http://{ip}:5000"
    img = qrcode.make(url)
    img.save("qr.png")
    return send_file("qr.png")

if __name__ == "__main__":
    ip = get_local_ip()
    print(f"\n✅ NexBridge çalışıyor!")
    print(f"📱 Telefonda şu adresi aç: http://{ip}:5000")
    print(f"🔗 QR kod için: http://{ip}:5000/qr\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
