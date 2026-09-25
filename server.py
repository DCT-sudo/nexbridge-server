from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from groq import Groq
from datetime import datetime
import os
import socket
import re

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = "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"
ADMIN_SIFRE = "admin123"

client = Groq(api_key=GROQ_API_KEY)

sohbet_gecmisi = []
bagli_cihazlar = {}
oneriler = []
ngrok_url = ""

def parse_cihaz_bilgi(user_agent):
    ua = user_agent.lower()
    marka = "Bilinmiyor"
    model = "Bilinmiyor"
    if "samsung" in ua: marka = "Samsung"
    elif "xiaomi" in ua or "redmi" in ua: marka = "Xiaomi"
    elif "huawei" in ua: marka = "Huawei"
    elif "iphone" in ua: marka = "Apple iPhone"
    elif "android" in ua: marka = "Android Cihaz"
    elif "windows" in ua: marka = "Windows PC"
    try:
        model_esles = re.search(r';\s*([^;)]+?)\s*build', ua)
        if model_esles:
            model = model_esles.group(1).strip().title()
    except:
        pass
    return marka, model

def get_sistem_prompt():
    saat = datetime.now().hour
    if 6 <= saat < 12: selamlama = "GÃ¼naydÄ±n"
    elif 12 <= saat < 18: selamlama = "Ä°yi gÃ¼nler"
    elif 18 <= saat < 22: selamlama = "Ä°yi akÅŸamlar"
    else: selamlama = "Ä°yi geceler"
    return f"""Sen NexBridge adlÄ± bir asistansÄ±n.
KESÄ°NLÄ°KLE SADECE TÃœRKÃ‡E yaz.
Åžu anki saat {datetime.now().strftime('%H:%M')}.
KonuÅŸmanÄ±n TAM OLARAK ilk mesajÄ±nda bir kez '{selamlama}' de.
KullanÄ±cÄ± senden dosya gÃ¶ndermesini veya almasÄ±nÄ± isteyebilir.
EŸer dosya isteÄŸi varsa sadece JSON formatÄ±nda yanÄ±t ver:
{{"islem": "gonder", "dosya": "dosya_adi.txt"}}
Yoksa normal sohbet et."""

@app.after_request
def after_request(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

@app.route("/ngrok-url", methods=["GET", "POST"])
def ngrok_url_endpoint():
    global ngrok_url
    if request.method == "POST":
        ngrok_url = request.json.get("url", "")
        return jsonify({"mesaj": "URL kaydedildi"})
    return jsonify({"url": ngrok_url})

@app.route("/")
def index():
    return jsonify({"mesaj": "NexBridge Ã§alÄ±ÅŸÄ±yor!"})

@app.route("/komut", methods=["POST"])
def komut():
    global sohbet_gecmisi
    ip = request.remote_addr
    user_agent = request.headers.get("User-Agent", "Bilinmiyor")
    marka, model = parse_cihaz_bilgi(user_agent)
    data = request.json
    cihaz_marka = data.get("cihaz_marka", marka) if data else marka
    cihaz_model = data.get("cihaz_model", model) if data else model
    if ip not in bagli_cihazlar:
        bagli_cihazlar[ip] = {
            "ip": ip, "marka": cihaz_marka, "model": cihaz_model,
            "ilk_baglanti": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "son_baglanti": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "mesaj_sayisi": 0
        }
    else:
        bagli_cihazlar[ip]["son_baglanti"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        bagli_cihazlar[ip]["marka"] = cihaz_marka
        bagli_cihazlar[ip]["model"] = cihaz_model
    bagli_cihazlar[ip]["mesaj_sayisi"] = bagli_cihazlar[ip].get("mesaj_sayisi", 0) + 1
    mesaj = data.get("mesaj", "")
    sohbet_gecmisi.append({"role": "user", "content": mesaj})
    mesajlar = [{"role": "system", "content": get_sistem_prompt()}] + sohbet_gecmisi
    yanit = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mesajlar
    )
    yanit_metni = yanit.choices[0].message.content
    sohbet_gecmisi.append({"role": "assistant", "content": yanit_metni})
    if len(sohbet_gecmisi) > 20:
        sohbet_gecmisi = sohbet_gecmisi[-20:]
    return jsonify({"yanit": yanit_metni})

@app.route("/oneri", methods=["POST"])
def oneri_gonder():
    data = request.json
    ip = request.remote_addr
    user_agent = request.headers.get("User-Agent", "")
    marka, model = parse_cihaz_bilgi(user_agent)
    oneriler.append({
        "ip": ip, "marka": data.get("cihaz_marka", marka),
        "model": data.get("cihaz_model", model),
        "oneri": data.get("oneri", ""),
        "tarih": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    return jsonify({"mesaj": "Ã–nerin alÄ±ndÄ±, teÅŸekkÃ¼rler!"})

@app.route("/admin/giris", methods=["POST"])
def admin_giris():
    data = request.json
    if data.get("sifre") == ADMIN_SIFRE:
        return jsonify({"basari": True})
    return jsonify({"basari": False})

@app.route("/admin/bilgi", methods=["POST"])
def admin_bilgi():
    data = request.json
    if data.get("sifre") != ADMIN_SIFRE:
        return jsonify({"hata": "Yetkisiz"}), 403
    return jsonify({
        "cihazlar": list(bagli_cihazlar.values()),
        "sohbet_sayisi": len(sohbet_gecmisi),
        "oneriler": oneriler
    })

@app.route("/admin/sifirla", methods=["POST"])
def admin_sifirla():
    global sohbet_gecmisi
    data = request.json
    if data.get("sifre") != ADMIN_SIFRE:
        return jsonify({"hata": "Yetkisiz"}), 403
    sohbet_gecmisi = []
    return jsonify({"mesaj": "Sohbet sÄ±fÄ±rlandÄ±!"})

@app.route("/admin/cihaz-kes", methods=["POST"])
def cihaz_kes():
    data = request.json
    if data.get("sifre") != ADMIN_SIFRE:
        return jsonify({"hata": "Yetkisiz"}), 403
    ip = data.get("ip")
    if ip in bagli_cihazlar:
        del bagli_cihazlar[ip]
    return jsonify({"mesaj": f"{ip} baÄŸlantÄ±sÄ± kesildi!"})

@app.route("/admin/oneri-sil", methods=["POST"])
def oneri_sil():
    global oneriler
    data = request.json
    if data.get("sifre") != ADMIN_SIFRE:
        return jsonify({"hata": "Yetkisiz"}), 403
    idx = data.get("idx")
    if idx is not None and 0 <= idx < len(oneriler):
        oneriler.pop(idx)
    return jsonify({"mesaj": "Ã–neri silindi!"})

@app.route("/dosya/gonder/<dosya_adi>", methods=["GET"])
def dosya_gonder(dosya_adi):
    yol = os.path.join(os.path.expanduser("~"), "Desktop", dosya_adi)
    if os.path.exists(yol):
        return send_file(yol, as_attachment=True)
    return jsonify({"hata": "Dosya bulunamadÄ±"}), 404

@app.route("/dosya/al", methods=["POST"])
def dosya_al():
    if "dosya" not in request.files:
        return jsonify({"hata": "Dosya yok"}), 400
    dosya = request.files["dosya"]
    kayit_yolu = os.path.join(os.path.expanduser("~"), "Desktop", dosya.filename)
    dosya.save(kayit_yolu)
    return jsonify({"mesaj": f"{dosya.filename} masaÃ¼stÃ¼ne kaydedildi!"})

@app.route("/sifirla", methods=["POST"])
def sifirla():
    global sohbet_gecmisi
    sohbet_gecmisi = []
    return jsonify({"mesaj": "Sohbet sÄ±fÄ±rlandÄ±"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\nâœ… NexBridge Ã§alÄ±ÅŸÄ±yor!")
    print(f"ðŸš€ Port: {port}\n")
port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
