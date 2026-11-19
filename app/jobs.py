"""คิวงาน: รันทีละงาน, หยุดได้, รออนุมัติบทได้"""
import subprocess
import threading
import time
import traceback
import uuid
from collections import deque

from . import core, pipeline

MAX_LOG = 400


class Ctx:
    def __init__(self, mgr, job):
        self.mgr, self.job, self.episode = mgr, job, None

    def log(self, msg):
        self.mgr._log(self.job, msg)

    def stage(self, text):
        self.job["stage"] = text
        self.mgr._save()

    def progress(self, pct):
        self.job["progress"] = round(min(100, max(0, pct)), 1)

    def cost(self, usd):
        if usd:
            self.job["cost_usd"] = round(self.job.get("cost_usd", 0) + usd, 6)
            core.add_cost(self.job["project"], usd)

    def check(self):
        if self.job.get("_stop"):
            raise pipeline.Stopped()

    def wait_approval(self, project, ep):
        self.job["status"] = "review"
        self.job["review"] = {"project": project, "ep": ep}
        self.log(f"⏸️ รอตรวจบทตอน {ep} (ไปที่ สั่งงาน → ตรวจบท)")
        self.mgr._save(force=True)
        while not self.job.get("_approved"):
            self.check()
            time.sleep(1)
        self.job["_approved"] = False
        self.job["review"] = None
        self.job["status"] = "running"
        self.log("▶️ อนุมัติบทแล้ว ทำต่อ")

    def run(self, cmd, label, cwd=None):
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        self.mgr.proc = proc
        try:
            while proc.poll() is None:
                if self.job.get("_stop"):
                    proc.kill()
                    proc.wait()
                    raise pipeline.Stopped()
                time.sleep(0.3)
            err = proc.stderr.read() if proc.stderr else ""
            if proc.returncode != 0:
                if "No module named edge_tts" in err:
                    raise RuntimeError("ยังไม่ได้ติดตั้งเสียงฟรี (edge-tts) → รันช่อง 2 ใน Colab แล้วกดทำต่อ")
                if "edge" in label and ("403" in err or "Connect" in err or "WSServerHandshake" in err):
                    raise RuntimeError("เชื่อมต่อเสียงฟรี Edge ไม่ได้ ลองใหม่อีกครั้ง หรือเปลี่ยนเสียงเป็น Gemini/ปิดเสียง")
                raise RuntimeError(f"{label} ล้มเหลว: {err.strip()[-800:]}")
        finally:
            self.mgr.proc = None


class JobManager:
    def __init__(self):
        self.jobs = {}
        self.order = []
        self.queue = deque()
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.current = None
        self.proc = None
        self._load()
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------- persistence ----------
    def _public(self, j):
        return {k: v for k, v in j.items() if not k.startswith("_")}

    def _save(self, force=False):
        now = time.time()
        if not force and now - getattr(self, "_last_save", 0) < 3:
            return  # กันเขียน Drive ถี่เกินไป
        self._last_save = now
        with self.lock:
            data = [self._public(self.jobs[i]) for i in self.order[-100:]]
        try:
            core.write_json(core.JOBS_FILE, data)
        except Exception:
            pass

    def _load(self):
        for j in core.read_json(core.JOBS_FILE, []) or []:
            if j.get("status") in ("running", "queued", "review"):
                j["status"] = "interrupted"
                j.setdefault("logs", []).append(f"{time.strftime('%H:%M:%S')} ⚠️ งานถูกตัดเพราะ Colab/เซิร์ฟเวอร์รีสตาร์ท กด 'ทำต่อ' ได้")
            self.jobs[j["id"]] = j
            self.order.append(j["id"])

    def _log(self, job, msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(f"[{job['project']}] {line}", flush=True)
        with self.lock:
            job["logs"].append(line)
            if len(job["logs"]) > MAX_LOG:
                del job["logs"][: len(job["logs"]) - MAX_LOG]
        self._save()

    # ---------- API ----------
    def submit(self, project, count=1):
        if not core.get_project(project):
            raise ValueError("ไม่พบโปรเจกต์")
        count = max(1, min(50, int(count)))
        job = {
            "id": uuid.uuid4().hex[:8], "project": project, "count": count, "done": 0,
            "status": "queued", "stage": "รอคิว", "progress": 0, "episode": None,
            "cost_usd": 0.0, "created": time.time(), "started": None, "finished": None,
            "error": None, "review": None, "logs": [],
        }
        with self.lock:
            self.jobs[job["id"]] = job
            self.order.append(job["id"])
            self.queue.append(job["id"])
        self._log(job, f"📥 เข้าคิว: ทำ {count} ตอน")
        self.wake.set()
        return self._public(job)

    def stop(self, job_id):
        with self.lock:
            j = self.jobs.get(job_id)
            if not j:
                raise ValueError("ไม่พบงาน")
            if j["status"] == "queued":
                if job_id in self.queue:
                    self.queue.remove(job_id)
                j["status"] = "stopped"
                j["stage"] = "ยกเลิกก่อนเริ่ม"
            elif j["status"] in ("running", "review"):
                j["_stop"] = True
                j["stage"] = "กำลังหยุด..."
        self._save(force=True)
        return self._public(j)

    def stop_all(self):
        with self.lock:
            ids = [i for i in self.order if self.jobs[i]["status"] in ("queued", "running", "review")]
        for i in ids:
            self.stop(i)
        return len(ids)

    def approve(self, job_id):
        j = self.jobs.get(job_id)
        if not j or j["status"] != "review":
            raise ValueError("งานนี้ไม่ได้รอตรวจบท")
        j["_approved"] = True
        return self._public(j)

    def resume(self, job_id):
        j = self.jobs.get(job_id)
        if not j:
            raise ValueError("ไม่พบงาน")
        remaining = max(1, j["count"] - j.get("done", 0))
        return self.submit(j["project"], remaining)

    def list(self, limit=50):
        with self.lock:
            return [self._public(self.jobs[i]) for i in reversed(self.order[-limit:])]

    def get(self, job_id):
        j = self.jobs.get(job_id)
        return self._public(j) if j else None

    def has_pending(self, project):
        with self.lock:
            return any(self.jobs[i]["project"] == project and self.jobs[i]["status"] in ("queued", "running", "review")
                       for i in self.order)

    def busy(self):
        return self.current is not None

    def queue_len(self):
        return len(self.queue)

    # ---------- worker ----------
    def _worker(self):
        while True:
            self.wake.wait(2)
            self.wake.clear()
            with self.lock:
                if not self.queue:
                    continue
                jid = self.queue.popleft()
                job = self.jobs[jid]
            self.current = jid
            ctx = Ctx(self, job)
            job.update(status="running", started=time.time())
            try:
                for _ in range(job["count"] - job["done"]):
                    ctx.check()
                    ep = core.next_episode(job["project"])
                    job["episode"] = ep
                    job["progress"] = 0
                    self._log(job, f"🚀 เริ่ม EP {ep}")
                    pipeline.run_episode(ctx, job["project"], ep)
                    job["done"] += 1
                    job["progress"] = 100
                job.update(status="done", stage=f"เสร็จ EP {job['episode']}")
            except pipeline.Stopped:
                job.update(status="stopped", stage="หยุดแล้ว (ทำต่อได้ ไม่เสียงานที่ทำไปแล้ว)")
                self._log(job, "⏹️ หยุดงานแล้ว")
            except Exception as e:
                job.update(status="error", stage="ผิดพลาด", error=str(e))
                self._log(job, f"❌ {e}")
                traceback.print_exc()
            finally:
                job["finished"] = time.time()
                job["review"] = None
                self.current = None
                self._save(force=True)
                if self.queue:
                    self.wake.set()
