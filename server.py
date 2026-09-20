from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from groq import Groq
from datetime import datetime
import os
import qrcode
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

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

def parse_cihaz_bilgi(user_agent):
    ua = user_agent.lower()
    marka = "Bilinmiyor"
    model = "Bilinmiyor"
    if "samsung" in ua:
        marka = "Samsung"
    elif "xiaomi" in ua or "redmi" in ua or "miui" in ua:
        marka = "Xiaomi"
    elif "huawei" in ua:
        marka = "Huawei"
    elif "iphone" in ua:
        marka = "Apple iPhone"
    elif "oppo" in ua:
        marka = "Oppo"
    elif "vivo" in ua:
        marka = "Vivo"
    elif "oneplus" in ua:
        marka = "OnePlus"
    elif "realme" in ua:
        marka = "Realme"
    elif "motorola" in ua or "moto" in ua:
        marka = "Motorola"
    elif "lg" in ua:
        marka = "LG"
    elif "android" in ua:
        marka = "Android Cihaz"
    elif "windows" in ua:
        marka = "Windows PC"
    try:
        model_esles = re.search(r';\s*([^;)]+?)\s*build', ua)
        if model_esles:
            model = model_esles.group(1).strip().title()
    except:
        pass
    return marka, model

def get_sistem_prompt():
    saat = datetime.now().hour
    if 6 <= saat < 12:
        selamlama = "Günaydın"
    elif 12 <= saat < 18:
        selamlama = "İyi günler"
    elif 18 <= saat < 22:
        selamlama = "İyi akşamlar"
    else:
        selamlama = "İyi geceler"
    return f"""Sen NexBridge adlı bir asistansın.
KESİNLİKLE SADECE TÜRKÇE yaz. Tek bir İngilizce veya başka yabancı dil kelimesi bile kullanma.
Şu anki saat {datetime.now().strftime('%H:%M')}.
Konuşmanın TAM OLARAK ilk mesajında bir kez '{selamlama}' de. Sonraki hiçbir mesajda selamlama yapma.
Kullanıcının söylediklerini dikkatlice dinle ve konuya uygun yanıt ver. Empati göster, kendi konularına saptırma.
Kullanıcı senden dosya göndermesini veya almasını isteyebilir.
Eğer dosya isteği varsa sadece JSON formatında yanıt ver:
{{"islem": "gonder", "dosya": "dosya_adi.txt"}}
veya
{{"islem": "al", "dosya": "dosya_adi.txt"}}
Yoksa normal sohbet et. Hata durumlarında 'Sanırım internet bağlantımda sıkıntı var' veya 'Biraz yoruldum, bir dakika' gibi doğal ifadeler kullan."""

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
    return render_template("index.html")

@app.route("/manifest.json")
def manifest():
    return render_template("manifest.json"), 200, {"Content-Type": "application/json"}

@app.route("/sw.js")
def sw():
    return render_template("sw.js"), 200, {"Content-Type": "application/javascript"}

@app.route("/komut", methods=["POST"])
def komut():
    global sohbet_gecmisi
    ip = request.remote_addr
    user_agent = request.headers.get("User-Agent", "Bilinmiyor")
    marka, model = parse_cihaz_bilgi(user_agent)
    cihaz_marka = request.json.get("cihaz_marka", marka) if request.json else marka
    cihaz_model = request.json.get("cihaz_model", model) if request.json else model
    if ip not in bagli_cihazlar:
        bagli_cihazlar[ip] = {
            "ip": ip,
            "marka": cihaz_marka,
            "model": cihaz_model,
            "ilk_baglanti": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "son_baglanti": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "mesaj_sayisi": 0
        }
        print(f"\n📱 Yeni cihaz bağlandı! IP: {ip} Marka: {cihaz_marka} Model: {cihaz_model}\n")
    else:
        bagli_cihazlar[ip]["son_baglanti"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        bagli_cihazlar[ip]["marka"] = cihaz_marka
        bagli_cihazlar[ip]["model"] = cihaz_model
    bagli_cihazlar[ip]["mesaj_sayisi"] = bagli_cihazlar[ip].get("mesaj_sayisi", 0) + 1
    data = request.json
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
    cihaz_marka = data.get("cihaz_marka", marka)
    cihaz_model = data.get("cihaz_model", model)
    oneriler.append({
        "ip": ip,
        "marka": cihaz_marka,
        "model": cihaz_model,
        "oneri": data.get("oneri", ""),
        "tarih": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    print(f"\n💡 Yeni öneri: {data.get('oneri')} ({ip})\n")
    return jsonify({"mesaj": "Önerin alındı, teşekkürler!"})

@app.route("/admin/giris", methods=["POST"])
def admin_giris():
    data = request.json
    if data.get("sifre") == ADMIN_SIFRE:
        return jsonify({"basari": True})
    return jsonify({"basari": False, "hata": "Yanlış şifre!"})

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
    return jsonify({"mesaj": "Sohbet sıfırlandı!"})

@app.route("/admin/cihaz-kes", methods=["POST"])
def cihaz_kes():
    data = request.json
    if data.get("sifre") != ADMIN_SIFRE:
        return jsonify({"hata": "Yetkisiz"}), 403
    ip = data.get("ip")
    if ip in bagli_cihazlar:
        del bagli_cihazlar[ip]
    return jsonify({"mesaj": f"{ip} bağlantısı kesildi!"})

@app.route("/admin/oneri-sil", methods=["POST"])
def oneri_sil():
    global oneriler
    data = request.json
    if data.get("sifre") != ADMIN_SIFRE:
        return jsonify({"hata": "Yetkisiz"}), 403
    idx = data.get("idx")
    if idx is not None and 0 <= idx < len(oneriler):
        oneriler.pop(idx)
    return jsonify({"mesaj": "Öneri silindi!"})

@app.route("/sifirla", methods=["POST"])
def sifirla():
    global sohbet_gecmisi
    sohbet_gecmisi = []
    return jsonify({"mesaj": "Sohbet sıfırlandı"})

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
    print(f"Bağlanan cihazlar ve öneriler burada görünecek...\n")
    app.run(host="0.0.0.0", port=5000, debug=False)