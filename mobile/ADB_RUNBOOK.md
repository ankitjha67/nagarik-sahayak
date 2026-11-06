# Nagarik Sahayak on a real phone — adb runbook

The app is a Capacitor wrapper around the existing React UI: the screens are
bundled into the APK and run in a WebView, and every API call goes to the
FastAPI backend over the network. For USB testing, the backend runs on your
laptop (ANKIT-DELL) and the phone reaches it through `adb reverse`.

This runbook is what you run on the laptop the phone is plugged into. The
cloud session that built the APK cannot see your USB — only you can run `adb`.

---

## 0. One-time prerequisites on the laptop

- **Android platform-tools** (gives you `adb`): https://developer.android.com/tools/releases/platform-tools — unzip, add to PATH.
- **On the phone:** Settings → About phone → tap *Build number* 7× to unlock Developer options → Developer options → enable **USB debugging**. Plug in over USB; when the phone asks, **Allow USB debugging** from this computer.
- Confirm the phone is seen:
  ```bash
  adb devices
  # List of devices attached
  # ABCD1234    device        <- not "unauthorized" or "offline"
  ```

## 1. Install the APK

Copy `app-debug.apk` (sent to you from the session) to the laptop, then:
```bash
adb install -r app-debug.apk        # -r reinstalls over a previous version
```
You should see `Success`. The app "Nagarik Sahayak" is now in the launcher.

## 2. Start the backend on the laptop

The app needs the backend reachable. Fastest end-to-end demo path uses
`DEMO_MODE` (OTP is always `123456`, speech falls back to a mock transcript),
so you can test the whole flow without SMS or a speech key.

```bash
# in the repo
cd backend

# MongoDB must be a replica set (Prisma uses transactions). If you don't have
# one, the quickest is Docker:
docker run -d --name ns-mongo -p 27017:27017 mongo:7 --replSet rs0
docker exec ns-mongo mongosh --quiet --eval 'rs.initiate({_id:"rs0",members:[{_id:0,host:"127.0.0.1:27017"}]})'

# Python deps (first time): pip install -r requirements.txt && python -m prisma generate
# Env — minimum for a device demo:
export MONGO_URL="mongodb://127.0.0.1:27017/nagarik_sahayak?replicaSet=rs0"
export DB_NAME=nagarik_sahayak
export CORS_ORIGINS="http://localhost"            # the app's WebView origin
export DEMO_MODE=true                              # OTP 123456 + mock STT
export AUTH_JWT_SECRET="dev-secret-at-least-32-characters-long-xxxx"
export DATA_ENCRYPTION_KEY="dev-encryption-key-change-me"
export IDENTITY_HASH_SALT="dev-salt-change-me"
export ADMIN_SECRET="dev-admin"

python -m prisma db push --skip-generate
python -m uvicorn server:app --host 127.0.0.1 --port 8001
```
Leave this running. (See `backend/.env.example` for every variable, including
real SMS providers and the 14 speech engines.)

## 3. Bridge the phone to the backend

With the phone connected, map the phone's own `localhost:8001` to the laptop's
backend:
```bash
adb reverse tcp:8001 tcp:8001
```
The APK was built with the backend URL `http://localhost:8001`, so nothing else
is needed. (`adb reverse` has to be re-run if you unplug/replug.)

**Prefer the LAN instead?** Skip `adb reverse`, find the laptop's IP
(`ipconfig` / `ip addr`, e.g. `192.168.1.5`), start uvicorn with
`--host 0.0.0.0`, and point the app at it without rebuilding — in the app,
open the browser console via `chrome://inspect` (step 6) and run:
```js
localStorage.setItem("ns_backend_url", "http://192.168.1.5:8001"); location.reload();
```

## 4. Launch and test on the phone

1. Open **Nagarik Sahayak**. Allow the microphone when asked.
2. **Login:** enter any Indian mobile number → OTP screen → enter `123456`
   (DEMO_MODE). You should land in the app with a session (a real JWT — check
   `adb logcat` shows the `/auth/verify-otp` call returning tokens).
3. **Scheme flow:** pick a scheme, answer the intake questions, generate the
   filled form, download the PDF.
4. **Voice:** tap the mic in chat, speak; in DEMO_MODE you get the mock
   transcript, otherwise configure a speech engine (step 7) and you get a real
   one. The engine actually used is shown in the toast and in the response.

## 5. Watch what the app is doing

```bash
adb logcat --pid=$(adb shell pidof -s app.nagariksahayak)      # app logs only
# or filter the WebView console + Capacitor bridge:
adb logcat | grep -iE "chromium|Capacitor|SystemWebChromeClient"
```

## 6. Inspect the WebView like a browser tab

A debug build is WebView-debuggable. On the laptop, open Chrome →
`chrome://inspect` → under *Remote Target* you'll see the app → **inspect**.
Full DevTools: console, network tab (see every API call and its status),
localStorage (`ns_access`, `ns_refresh`, `ns_backend_url`). This is the fastest
way to confirm auth and the backend URL.

## 7. Real speech on device (optional, drops the mock)

Set `DEMO_MODE=false` and give the backend at least one speech engine before
starting uvicorn, e.g. the free Government of India one:
```bash
export DEMO_MODE=false
export BHASHINI_USER_ID=...   BHASHINI_ULCA_KEY=...     # bhashini.gov.in
# or any other from backend/.env.example: GROQ_API_KEY, OPENAI_API_KEY, SARVAM_API_KEY, …
```
`GET http://localhost:8001/api/stt/providers` lists what is configured and the
order they'll be tried. With `DEMO_MODE=false` you also need a real OTP path —
set `SMS_PROVIDER` and its keys, or set `OTP_MOCK_CODE=123456` for a dev phone.

## 8. Rebuild after a change

```bash
cd frontend
REACT_APP_BACKEND_URL="http://localhost:8001" CI=false npx craco build
npx cap sync android
cd android && ./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `adb devices` shows `unauthorized` | Accept the "Allow USB debugging" prompt on the phone; re-plug. |
| App loads but every call fails | Backend not running, or `adb reverse` not set. Re-run step 3; check `chrome://inspect` network tab. |
| Login says "could not send code" | DEMO_MODE off with no SMS provider. Set `DEMO_MODE=true` or `OTP_MOCK_CODE`. |
| Mic does nothing | Permission denied — reinstall and Allow, or Settings → Apps → Nagarik Sahayak → Permissions → Microphone. |
| Voice returns 503 | No speech engine configured and not in DEMO_MODE. See step 7. |
| `CLEARTEXT ... not permitted` | You pointed at an IP not covered; the debug build permits all cleartext, so rebuild if you changed the network config. |
