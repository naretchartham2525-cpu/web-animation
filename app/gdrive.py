"""ลบไฟล์ใน Google Drive แบบถาวรทันที (ไม่ผ่านถังขยะ 30 วันของ Drive)

ลบผ่านโฟลเดอร์ที่ mount ใน Colab ไฟล์จะไปอยู่ในถังขยะของ Drive เสมอ → ใช้ Drive API ลบด้วย ID แทน
ต้องอนุญาตครั้งเดียวตอนเปิด Colab (auth.authenticate_user) · ไม่มีสิทธิ์ = ลบแบบปกติ (ไปถังขยะ Drive)
"""
import os
import shutil

SCOPES = ["https://www.googleapis.com/auth/drive"]


def file_id(path):
    try:
        return os.getxattr(str(path), "user.drive.id").decode()   # Colab DriveFS บอก ID ของไฟล์/โฟลเดอร์
    except (OSError, AttributeError):
        return ""


def _token():
    import google.auth
    from google.auth.transport.requests import Request
    creds, _ = google.auth.default(scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def delete_forever(path):
    """คืน True = หายถาวรจาก Drive แล้ว · False = ลบแบบปกติ (ไปถังขยะของ Drive)"""
    gone = False
    fid = file_id(path)
    if fid:
        try:
            import requests
            r = requests.delete(f"https://www.googleapis.com/drive/v3/files/{fid}",
                                params={"supportsAllDrives": "true"},
                                headers={"Authorization": f"Bearer {_token()}"}, timeout=60)
            gone = r.status_code in (200, 204, 404)
        except Exception:  # noqa: BLE001  ไม่มีสิทธิ์/ไม่มีไลบรารี → ลบแบบปกติ
            gone = False
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)
    return gone
