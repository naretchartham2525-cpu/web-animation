"""สตูดิโอเถื่อน: ขั้นตอนเปิดเว็บทั้งหมด (notebook เรียกไฟล์นี้หลังดึงโค้ดล่าสุด)
แก้ขั้นตอนที่นี่ได้เลย ไม่ต้องให้ผู้ใช้คัดลอก notebook ใหม่"""
import os, subprocess, shutil
CODE = globals().get('CODE', '/content/web-animation')
print('✅ โค้ด:', subprocess.run(f'git -C {CODE} log -1 --format="%h %s (%cr)"', shell=True, capture_output=True, text=True).stdout.strip())

# ---------- 1) Google Drive + เทมเพลต ----------
from google.colab import drive
drive.mount('/content/drive')
ROOT = '/content/drive/MyDrive/AutoClip'
for d in ('skills', 'projects', 'fonts'):
    os.makedirs(f'{ROOT}/{d}', exist_ok=True)
# เทมเพลตใหม่ใน GitHub → เพิ่มลง Drive อัตโนมัติ (ไม่ทับของที่มีอยู่/ที่แก้เองในเว็บ)
added = []
for d in sorted(os.listdir(f'{CODE}/skills')):
    if not os.path.exists(f'{ROOT}/skills/{d}'):
        shutil.copytree(f'{CODE}/skills/{d}', f'{ROOT}/skills/{d}')
        added.append(d)
    else:
        # สกิลที่มีอยู่แล้ว: อัปเดต autoclip.json (ไฟล์ของระบบเรา) + เติมไฟล์ที่ขาด ไม่ทับไฟล์อื่น
        for base, _, files in os.walk(f'{CODE}/skills/{d}'):
            rel = os.path.relpath(base, f'{CODE}/skills/{d}')
            for fn in files:
                src = os.path.join(base, fn)
                dst = os.path.normpath(os.path.join(f'{ROOT}/skills/{d}', rel, fn))
                if fn == 'autoclip.json' and rel == '.' or not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
if added:
    print('➕ เพิ่มเทมเพลตใหม่จาก GitHub:', added)
print('✅ Drive:', ROOT)
print('   สกิล:', sorted(os.listdir(f'{ROOT}/skills')))
print('   โปรเจกต์:', sorted(os.listdir(f'{ROOT}/projects')))

# ---------- 2) ติดตั้งเครื่องมือ ----------
print('⏳ ติดตั้งเครื่องมือ (ครั้งแรกประมาณ 1-2 นาที)...')
import subprocess
subprocess.run('apt-get -qq update > /dev/null; apt-get -qq install -y fonts-thai-tlwg > /dev/null', shell=True)
subprocess.run('pip -q install flask edge-tts pythainlp', shell=True)
# ของที่สกิลแบบมีเอนจินต้องใช้ (อ่านจาก autoclip.json ของแต่ละสกิลใน Drive)
import glob, json as _json
need = set()
for f in glob.glob(f'{ROOT}/skills/*/autoclip.json'):
    try:
        need.update(_json.load(open(f, encoding='utf-8')).get('requirements') or [])
    except Exception as e:
        print('⚠️ อ่าน', f, 'ไม่ได้:', e)
if need:
    print('📦 ติดตั้งของที่สกิลต้องใช้:', ', '.join(sorted(need)))
    subprocess.run('pip -q install ' + ' '.join(sorted(need)), shell=True)
subprocess.run('fc-cache -f > /dev/null', shell=True)
print(subprocess.run('ffmpeg -version', shell=True, capture_output=True, text=True).stdout.splitlines()[0])
print('✅ ติดตั้งเสร็จ')

# ---------- 3) API key จาก Secrets ----------
import os, secrets as _s
from google.colab import userdata

def _get(name):
    try:
        v = userdata.get(name)
        return v.strip() if v else ''
    except Exception:
        return ''

key = _get('OPENROUTER_API_KEY')
if key:
    os.environ['OPENROUTER_API_KEY'] = key
    print('✅ OPENROUTER_API_KEY: โหลดแล้ว (' + key[:6] + '…)')
else:
    print('❌ ไม่พบ OPENROUTER_API_KEY → แถบซ้าย 🔑 Secrets → Add new secret → เปิด Notebook access')

pw = _get('AUTOCLIP_PASSWORD')
if not pw:
    pw = _s.token_urlsafe(8)
    print('⚠️ ไม่ได้ตั้ง AUTOCLIP_PASSWORD → สุ่มรหัสให้ (เปลี่ยนทุกครั้งที่รัน):', pw)
else:
    print('✅ AUTOCLIP_PASSWORD: โหลดแล้ว')
os.environ['AUTOCLIP_PASSWORD'] = pw

# ---------- 4) เปิดเว็บ + Cloudflare Tunnel ----------
import subprocess, time, re, os, requests

os.environ['AUTOCLIP_ROOT'] = ROOT
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'
subprocess.run('pkill -f "app.server"; pkill -f cloudflared', shell=True)
time.sleep(1)

server = subprocess.Popen(['python', '-m', 'app.server', '--port', '8000'], cwd=CODE,
                          stdout=open('/content/server.log', 'w'), stderr=subprocess.STDOUT, env=os.environ.copy())
for _ in range(40):
    try:
        requests.get('http://127.0.0.1:8000/api/ping', timeout=1); break
    except Exception:
        time.sleep(1)
else:
    print(open('/content/server.log').read()[-3000:])
    raise SystemExit('❌ เซิร์ฟเวอร์ไม่ขึ้น ดู log ด้านบน')

CF = '/content/cloudflared'
if not os.path.exists(CF):
    subprocess.run(f'wget -q -O {CF} https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x {CF}', shell=True)
tunnel = subprocess.Popen([CF, 'tunnel', '--no-autoupdate', '--url', 'http://127.0.0.1:8000'],
                          stdout=open('/content/cf.log', 'w'), stderr=subprocess.STDOUT)
url = None
for _ in range(60):
    m = re.search(r'https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com', open('/content/cf.log').read())
    if m:
        url = m.group(0); break
    time.sleep(1)

print('=' * 60)
if url:
    print('🌐 เปิดเว็บที่:', url)
    print('🔒 รหัสผ่าน: ใช้ AUTOCLIP_PASSWORD (หรือรหัสที่สุ่มให้ด้านบน)')
    print('⏳ ถ้าเปิดแล้วขึ้น error ให้รอ 10-20 วินาทีแล้วรีเฟรช')
else:
    print('❌ ไม่ได้ URL'); print(open('/content/cf.log').read()[-2000:])
print('=' * 60)
print('⚠️ ห้ามปิดแท็บ Colab นี้ ถ้าปิด เว็บจะหยุด (งานที่ทำแล้วอยู่ใน Drive ไม่หาย)')
